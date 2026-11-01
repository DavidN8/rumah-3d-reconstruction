"""CPU-only feasibility measurements for architectural planes; never edits geometry."""
import os
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[key]='4'
if os.name=='nt':
    import ctypes
    kernel=ctypes.windll.kernel32;kernel.GetCurrentProcess.restype=ctypes.c_void_p
    process=kernel.GetCurrentProcess();allowed=ctypes.c_size_t();system=ctypes.c_size_t()
    kernel.GetProcessAffinityMask.argtypes=[ctypes.c_void_p,ctypes.POINTER(ctypes.c_size_t),ctypes.POINTER(ctypes.c_size_t)]
    kernel.SetProcessAffinityMask.argtypes=[ctypes.c_void_p,ctypes.c_size_t]
    if not kernel.GetProcessAffinityMask(process,ctypes.byref(allowed),ctypes.byref(system)):raise OSError('Cannot inspect CPU affinity')
    bits=[1<<i for i in range(allowed.value.bit_length()) if allowed.value&(1<<i)][:8]
    if not kernel.SetProcessAffinityMask(process,sum(bits)):raise OSError('Cannot bound CPU affinity')
from pathlib import Path
import argparse,hashlib,json,re,sys,time
import numpy as np
import cv2
from scipy.spatial import ConvexHull,Delaunay,cKDTree
from PIL import Image,ImageDraw

HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(HERE/'qa-deps'),str(HERE.parent/'osmo-reconstruct-20261031')]
import trimesh
from trimesh.ray.ray_pyembree import RayMeshIntersector
from seed_fisheye import read_model,qvec_to_rotmat,Fisheye
RUN=Path(r'C:\Users\bombe\OneDrive\Documents\ChatGPT\Ruang Kamare\roomscan-reconstruction\data\20261031_OSMO360\lite-v1')
SOURCE=RUN/'exports/osmo-lite-trusted-source.glb'
parser=argparse.ArgumentParser();parser.add_argument('--source',type=Path,default=SOURCE)
parser.add_argument('--output-prefix',default='plane-audit');parser.add_argument('--reference-planes',type=Path)
args=parser.parse_args();SOURCE=args.source.resolve()
if not re.fullmatch(r'plane-audit(?:-[a-z0-9]+)*',args.output_prefix):raise ValueError('Use a plane-audit-* output prefix')
rng=np.random.default_rng(20261031)
started=time.monotonic()

def stats(values):
    values=np.asarray(values);values=values[np.isfinite(values)]
    return {'count':len(values),'median':float(np.median(values)),'p90':float(np.percentile(values,90)),
            'p95':float(np.percentile(values,95)),'maximum':float(values.max())} if len(values) else {'count':0}

def refit(xyz,normal,offset):
    for _ in range(4):
        keep=np.abs(xyz@normal+offset)<.025
        if keep.sum()<50:return None
        center=np.median(xyz[keep],axis=0)
        _,_,vh=np.linalg.svd(xyz[keep]-center,full_matrices=False)
        normal=vh[-1];offset=-center@normal
    return normal,float(offset),keep

def basis(normal):
    u=np.cross([0,1,0],normal)
    if np.linalg.norm(u)<.1:u=np.cross([1,0,0],normal)
    u/=np.linalg.norm(u);v=np.cross(normal,u);return np.array([u,v])

print('Loading strict normalized SfM and accepted point IDs',flush=True)
cameras,images,points=read_model(RUN/'dataset/sparse/0')
cached=np.load(HERE/'qa-good-sfm.npz',allow_pickle=False)
ids=cached['point_ids'];xyz=np.array([points[int(pid)]['xyz'] for pid in ids])
assert np.max(np.abs(xyz-cached['points']))<1e-10
lookup={int(pid):i for i,pid in enumerate(ids)}
counts=np.zeros(len(ids),int);obs_point=[];obs_camera=[];obs_image=[];image_names=[]
for image_no,im in enumerate(sorted(images.values(),key=lambda im:im['name'])):
    selected=[(j,lookup[int(pid)]) for j,pid in enumerate(im['point3D_ids']) if int(pid) in lookup]
    if not selected:continue
    j,pi=np.array(selected,dtype=int).T
    camera=cameras[im['camera_id']];rot=qvec_to_rotmat(im['qvec']);center=-rot.T@im['tvec']
    pc=xyz[pi]@rot.T+im['tvec'];prediction,valid=Fisheye(camera).project(pc)
    observation=im['points2D_xy'][j];err=np.linalg.norm(prediction-observation,axis=1)
    angle=np.degrees(np.arctan2(np.linalg.norm(pc[:,:2],axis=1),pc[:,2]));xy=np.rint(observation).astype(int)
    mask=cv2.imread(str(RUN/'dataset/masks'/Path(im['name']).with_suffix('.png')),0)
    inside=(xy[:,0]>=0)&(xy[:,0]<camera['width'])&(xy[:,1]>=0)&(xy[:,1]<camera['height'])
    take=np.flatnonzero(valid&inside&(err<=2)&(angle<=85))
    take=take[mask[xy[take,1],xy[take,0]]>127]
    np.add.at(counts,pi[take],1)
    obs_point.extend(pi[take]);obs_camera.extend([center]*len(take));obs_image.extend([image_no]*len(take));image_names.append(im['name'])
good=counts>=3;old_to_new=np.full(len(ids),-1,int);old_to_new[good]=np.arange(good.sum())
op=np.array(obs_point,int);oc=np.array(obs_camera);oi=np.array(obs_image,int);take=good[op]
op=old_to_new[op[take]];oc=oc[take];oi=oi[take]
xyz=xyz[good];ids=ids[good];counts=counts[good]
colors=np.array([points[int(pid)]['rgb'] for pid in ids]);white=(colors.min(1)>140)&((colors.max(1)-colors.min(1))<40)
print('Verified support',len(xyz),'points /',len(op),'masked low-error observations',flush=True)

# Voxelized scores keep heavily textured patches from winning merely by density.
_,voxel=np.unique(np.floor(xyz/.05).astype(int),axis=0,return_index=True)
vox=xyz[voxel];available=np.ones(len(vox),bool);planes=[]
for _ in range(4):
    sample=vox[available]
    if len(sample)<150:break
    bins=np.floor(sample[:,1]/.015).astype(int)
    values,n=np.unique(bins,return_counts=True);height=(values[np.argmax(n)]+.5)*.015
    result=refit(sample,np.array([0.,1.,0.]),-height)
    if result is None:break
    normal,offset,keep=result
    available[np.flatnonzero(available)[keep]]=False
    if abs(normal[1])<.97 or keep.sum()<80:continue
    if normal[1]<0:normal=-normal;offset=-offset
    planes.append(('horizontal',normal,offset))
available=(vox[:,1]>.12)&(vox[:,1]<3.0)
for _ in range(8):
    sample=vox[available]
    if len(sample)<100:break
    best=(0,None,None)
    for batch in range(20):
        pair=rng.integers(0,len(sample),(64,2));delta=sample[pair[:,1]]-sample[pair[:,0]]
        normals=np.column_stack([delta[:,2],np.zeros(len(delta)),-delta[:,0]])
        lengths=np.linalg.norm(normals,axis=1);valid=lengths>.25
        normals=normals[valid]/lengths[valid,None];offsets=-np.sum(sample[pair[valid,0]]*normals,axis=1)
        scores=np.sum(np.abs(sample@normals.T+offsets)<.025,axis=0)
        if len(scores) and scores.max()>best[0]:
            k=int(scores.argmax());best=(int(scores[k]),normals[k],float(offsets[k]))
    if best[0]<80:break
    result=refit(sample,best[1],best[2])
    if result is None:break
    normal,offset,keep=result
    available[np.flatnonzero(available)[keep]]=False
    if abs(normal[1])>.15 or keep.sum()<80:continue
    if normal[np.argmax(np.abs(normal))]<0:normal=-normal;offset=-offset
    planes.append(('vertical',normal,offset))

if args.reference_planes:
    reference=json.loads(args.reference_planes.read_text(encoding='utf-8'))
    planes=[(p['kind'],np.array(p['normal']),p['offset']) for p in reference['planes']]
print('Plane hypotheses',len(planes),'; loading comparison CPU mesh',flush=True)
mesh=trimesh.load(SOURCE,force='mesh',process=False)
surface,face_no=trimesh.sample.sample_surface(mesh,200000,seed=20261031)
normals=np.asarray(mesh.face_normals)[face_no]
horizontal_surface=surface[np.abs(normals[:,1])>.95]
height_bin=np.floor(horizontal_surface[:,1]/.05).astype(int)
height_value,height_number=np.unique(height_bin,return_counts=True)
ceiling_tests=[]
for k in ([] if args.reference_planes else np.argsort(-height_number)[:12]):
    height=float((height_value[k]+.5)*.05)
    if height<1.8:continue
    if any(kind=='horizontal' and abs(-offset/normal[1]-height)<.10 for kind,normal,offset in planes):continue
    fit=refit(vox,np.array([0.,1.,0.]),-height)
    test={'mesh_height_seed':height,'strict_voxel_fit_found':fit is not None}
    if fit is not None:
        normal,offset,keep=fit;test['support_voxels']=int(keep.sum());test['normal']=normal.tolist();test['offset']=offset
        if abs(normal[1])>.97 and keep.sum()>=50:
            if normal[1]<0:normal=-normal;offset=-offset
            planes.append(('horizontal',normal,offset));test['included']=True
    ceiling_tests.append(test)
intersector=RayMeshIntersector(mesh)
def ray_ranges(origins,directions):
    distance=np.full(len(origins),np.inf)
    for first in range(0,len(origins),4096):
        end=min(first+4096,len(origins));loc,ri,_=intersector.intersects_location(origins[first:end],directions[first:end],multiple_hits=False)
        if len(ri):distance[first+ri]=np.linalg.norm(loc-origins[first+ri],axis=1)
    return distance

rows=[];panels=[];grids={}
presets=json.loads((HERE.parent/'mobile-20261029/legacy-osmo-cameras.json').read_text(encoding='utf-8'))['presets']
photo_views=[]
for preset in presets:
    source=Path(preset['sourceFile']);rgb=cv2.cvtColor(cv2.imread(str(source)),cv2.COLOR_BGR2RGB)
    blurred=cv2.blur(rgb.astype(np.float32),(5,5))
    valid=cv2.imread(str(source.with_name(source.stem+'-valid.png')),0)
    q=preset['quaternion'];rotation=qvec_to_rotmat([q[3],*q[:3]])
    photo_views.append((preset,rotation,blurred,valid))
for number,(kind,normal,offset) in enumerate(planes):
    residual=np.abs(xyz@normal+offset);ix=np.flatnonzero(residual<.025)
    if len(ix)<100:continue
    axes=basis(normal);center=np.median(xyz[ix],axis=0);center-=(center@normal+offset)*normal;uv=(xyz[ix]-center)@axes.T
    hull=ConvexHull(uv);extent=np.ptp(uv,axis=0)
    if hull.volume<.3 or min(extent)<.3:continue
    hulltest=Delaunay(uv[hull.vertices]);mesh_uv=(surface-center)@axes.T
    near=(np.abs(surface@normal+offset)<.20)&(np.abs(normals@normal)>.85)&(hulltest.find_simplex(mesh_uv)>=0)
    mesh_residual=np.abs(surface[near]@normal+offset)
    # Spatially separate refits reveal tilt/offset instability inside the support.
    split=uv[:,0]<np.median(uv[:,0]);halves=[]
    for half in (split,~split):
        fitted=refit(xyz[ix[half]],normal,offset)
        if fitted is not None:halves.append(fitted[:2])
    angle=float(np.degrees(np.arccos(np.clip(abs(halves[0][0]@halves[1][0]),0,1)))) if len(halves)==2 else None
    step=.05;low=np.floor(uv.min(0)/step)*step;high=np.ceil(uv.max(0)/step)*step
    nu,nv=np.maximum(1,np.ceil((high-low)/step).astype(int))
    uu,vv=np.meshgrid(np.arange(nu),np.arange(nv));griduv=low+np.column_stack([uu.ravel()+.5,vv.ravel()+.5])*step
    inside=hulltest.find_simplex(griduv)>=0;grid=center+griduv@axes
    distance=np.full(len(grid),np.inf);signed_distance=np.full(len(grid),np.nan)
    for sign in (-1,1):
        origins=grid[inside]+sign*normal*.25;direction=np.tile(-sign*normal,(len(origins),1))
        hit=ray_ranges(origins,direction);value=sign*(.25-hit)
        better=np.flatnonzero(np.isfinite(hit)&(np.abs(value)<distance[inside]));where=np.flatnonzero(inside)[better]
        distance[where]=np.abs(value[better]);signed_distance[where]=value[better]
    covered=inside&(distance<=.05);gaps=inside&~covered
    # A trusted feature observed beyond the proposed plane is direct evidence
    # against closing that ray: a door/window/open edge or a finite plane extent.
    vector=xyz[op]-oc;den=vector@normal;factor=-(oc@normal+offset)/np.where(np.abs(den)>1e-12,den,np.nan)
    crosses=np.isfinite(factor)&(factor>.02)&(factor<.98)&((1-factor)*np.linalg.norm(vector,axis=1)>.15)
    cp=oc[crosses]+factor[crosses,None]*vector[crosses];cuv=(cp-center)@axes.T
    cell=np.floor((cuv-low)/step).astype(int)
    inrange=(cell[:,0]>=0)&(cell[:,0]<nu)&(cell[:,1]>=0)&(cell[:,1]<nv)&(hulltest.find_simplex(cuv)>=0)
    cell=cell[inrange];cross_grid=np.zeros(len(grid),int);cross_points=np.zeros(len(grid),int)
    flat=cell[:,1]*nu+cell[:,0];np.add.at(cross_grid,flat,1)
    for index in np.unique(flat):cross_points[index]=len(np.unique(op[crosses][inrange][flat==index]))
    negative=cross_points>=2
    grids[f'plane_{number}_uv']=griduv
    grids[f'plane_{number}_signed']=signed_distance
    grids[f'plane_{number}_inside']=inside
    grids[f'plane_{number}_negative']=negative
    grids[f'plane_{number}_shape']=np.array([nv,nu])
    sparse_distance=cKDTree(uv).query(griduv,k=1)[0]
    nearby=gaps&(sparse_distance<=.10)&~negative
    candidate=np.flatnonzero(nearby)
    if len(candidate)>250:candidate=rng.choice(candidate,250,replace=False)
    photo_colors=np.full((len(candidate),len(photo_views),3),np.nan)
    for vi,(preset,rotation,blurred,valid_mask) in enumerate(photo_views):
        delta=grid[candidate]-np.array(preset['position']);pc=delta@rotation;z=-pc[:,2]
        fx,fy,cx,cy=preset['intrinsics'];pixels=np.column_stack([fx*pc[:,0]/np.maximum(z,1e-12)+cx,-fy*pc[:,1]/np.maximum(z,1e-12)+cy])
        xy=np.rint(pixels).astype(int);h,w=blurred.shape[:2]
        vis=(z>.1)&(xy[:,0]>=3)&(xy[:,0]<w-3)&(xy[:,1]>=3)&(xy[:,1]<h-3)
        local=np.flatnonzero(vis)
        if valid_mask is not None:local=local[valid_mask[xy[local,1],xy[local,0]]>127]
        if len(local):
            expected=np.linalg.norm(delta[local],axis=1);direction=delta[local]/expected[:,None]
            facing=np.abs(direction@normal)>.25
            hit=ray_ranges(np.tile(np.array(preset['position']),(len(local),1)),direction)
            local=local[(hit>=expected-.07)&facing]
            photo_colors[local,vi]=blurred[xy[local,1],xy[local,0]]
    photo_counts=np.isfinite(photo_colors[:,:,0]).sum(1);multi=photo_counts>=2
    color_deviation=[];photo_white=[]
    for local in np.flatnonzero(multi):
        rgb=photo_colors[local,np.isfinite(photo_colors[local,:,0])]
        color_deviation.append(float(np.sqrt(np.mean(np.var(rgb,axis=0)))))
        mean=rgb.mean(0);photo_white.append(bool(mean.min()>150 and np.ptp(mean)<40))
    observation_members=np.isin(op,ix)
    row={'plane':number,'kind':kind,'normal':normal.tolist(),'offset':float(offset),'center':center.tolist(),
      'support_points':len(ix),'support_observations':int(observation_members.sum()),'distinct_images':len(np.unique(oi[observation_members])),
      'white_support_fraction':float(white[ix].mean()),'plane_hull_area':float(hull.volume),'local_extents':extent.tolist(),
      'sparse_inlier_absolute_residual':stats(residual[ix]),'independent_spatial_half_normal_difference_degrees':angle,
      'baseline_surface_points_within_20cm_parallel_slab':int(near.sum()),'baseline_conditional_plane_residual':stats(mesh_residual),
      'baseline_conditional_within_2cm':float((mesh_residual<=.02).mean()) if len(mesh_residual) else None,
      'baseline_conditional_within_5cm':float((mesh_residual<=.05).mean()) if len(mesh_residual) else None,
      'grid_cell_size':step,'hull_grid_cells':int(inside.sum()),'mesh_supported_within_5cm_cells':int(covered.sum()),
      'missing_near_plane_cells':int(gaps.sum()),'missing_near_plane_area':float(gaps.sum()*step**2),
      'gap_cells_with_at_least2_distinct_background_feature_rays':int((gaps&negative).sum()),
      'gap_cells_with_sparse_plane_support_within10cm_and_no_negative_witness':int(nearby.sum()),
      'photo_checked_candidate_samples':len(candidate),'samples_visible_in_at_least2_of6_source_views':int(multi.sum()),
      'multiview_5x5_rgb_mean_std_255':stats(color_deviation),
      'multiview_bright_neutral_sample_fraction':float(np.mean(photo_white)) if photo_white else None,
      'negative_witness_observations':int(inrange.sum()),'maximum_negative_witness_count_per_cell':int(cross_grid.max()),
      'interpretation':'Convex-hull/slab figures include finite wall extents and real openings. Gap cells are not automatically repairable.'}
    rows.append(row)
    canvas=np.full((nv,nu,3),[43,48,55],np.uint8);canvas.reshape(-1,3)[inside]=[150,65,55];canvas.reshape(-1,3)[covered]=[65,125,85]
    canvas.reshape(-1,3)[nearby]=[210,165,45];canvas.reshape(-1,3)[gaps&negative]=[155,75,180]
    panel=Image.fromarray(np.flipud(canvas)).resize((700,300),Image.Resampling.NEAREST)
    title=Image.new('RGB',(700,345),(24,29,35));title.paste(panel,(0,45));draw=ImageDraw.Draw(title)
    draw.text((8,6),f'Plane {number}: {kind}; {len(ix)} tracks, {row["distinct_images"]} images; white {row["white_support_fraction"]:.0%}',fill='white')
    draw.text((8,23),f'Green mesh <5cm; red gap; purple background rays; yellow near sparse support',fill='white');panels.append(title)
    print('Plane',number,kind,'tracks',len(ix),'images',row['distinct_images'],'area',round(hull.volume,2),'gaps',gaps.sum(),'negative',int((gaps&negative).sum()),flush=True)

report={'source_mesh':str(SOURCE),'source_mesh_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
 'strict_sfm_points':len(xyz),'strict_masked_observations':len(op),'camera_model':'Native OPENCV_FISHEYE, 8 parameters; exact accepted normalized Y-up frame',
 'point_gate':'Cached accepted track>=4, then recomputed >=3 masked observations <=2px reprojection and theta<=85deg; zero writer point.error ignored',
 'units':'Approximate normalized world units from assumed1.5m median camera height; no measured centimetre accuracy claim',
 'mesh_faces':len(mesh.faces),'mesh_vertices':len(mesh.vertices),'area_weighted_surface_samples':len(surface),'planes':rows,
 'dominant_horizontal_mesh_height_bands':[],
 'mesh_informed_high_ceiling_seed_tests':ceiling_tests,
 'limits':['In-sample SfM support is not independent ground truth.','Planar furniture/doors can fit alongside walls; white RGB support is descriptive only.',
 'Convex hulls bridge actual openings and occlusion boundaries; missing cells must not be filled by hull alone.',
 'Conditional mesh residual excludes surfaces farther than20cm or normals differing >31.8deg, so it cannot validate arbitrary absent geometry.',
 'Six upright source views have limited wall/ceiling overlap. RGB agreement alone, especially on textureless white paint, cannot prove a proposed plane patch.',
 'Sparse point colors favor textured/dark corners and do not classify the material of the surrounding white wall.',
 'A background-track ray crossing a proposed patch is strong negative evidence; no such witness is not positive evidence that a wall exists.'],
 'geometry_mutated':False,'gpu_used':False,'linear_algebra_threads':4,'process_logical_cpu_affinity_maximum':8,'elapsed_seconds':time.monotonic()-started}
horizontal=surface[np.abs(normals[:,1])>.95]
band=np.floor(horizontal[:,1]/.05).astype(int);values,number=np.unique(band,return_counts=True)
for k in np.argsort(-number)[:12]:
    report['dominant_horizontal_mesh_height_bands'].append({'y_center':float((values[k]+.5)*.05),'area_sample_count':int(number[k])})
(HERE/(args.output_prefix+'-summary.json')).write_text(json.dumps(report,indent=2),encoding='utf-8')
np.savez_compressed(HERE/(args.output_prefix+'-grid.npz'),**grids)
if panels:
    sheet=Image.new('RGB',(1400,345*((len(panels)+1)//2)),(24,29,35))
    for j,panel in enumerate(panels):sheet.paste(panel,(j%2*700,j//2*345))
    sheet.save(HERE/(args.output_prefix+'-support.png'))
print(json.dumps({'planes':len(rows),'points':len(xyz),'observations':len(op),'seconds':report['elapsed_seconds']},indent=2))
