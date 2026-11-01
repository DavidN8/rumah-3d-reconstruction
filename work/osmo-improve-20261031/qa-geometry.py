"""CPU-only welded topology and sparse-observation visibility consistency.

No reconstruction, model edits or GPU use. Uses a fixed, masked, low-reprojection
sample of observations from the accepted main SfM component. The diagnostic is
in-sample consistency, not independent geometric ground truth.
"""
import os
os.environ['OMP_NUM_THREADS']='2'
os.environ['OPENBLAS_NUM_THREADS']='2'
from pathlib import Path
import argparse
import hashlib
import json
import sys
import time
import numpy as np
import cv2
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from scipy.spatial import cKDTree

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/'qa-deps'))
sys.path.insert(0,str(HERE.parent/'osmo-reconstruct-20261031'))
import trimesh
from seed_fisheye import read_model,qvec_to_rotmat,Fisheye
RUN=Path(r'C:\Users\bombe\OneDrive\Documents\ChatGPT\Ruang Kamare\roomscan-reconstruction\data\20261031_OSMO360\lite-v1')

def save(path,data):
    path=Path(path).resolve()
    if not path.is_relative_to(HERE) or not path.name.startswith('qa-'):
        raise ValueError('QA outputs must stay under this folder with qa- prefix')
    path.write_text(json.dumps(data,indent=2))

def fixed_rays():
    cache=HERE/'qa-fixed-rays.npz';meta=HERE/'qa-fixed-rays.json'
    if cache.exists():return dict(np.load(cache,allow_pickle=False)),json.loads(meta.read_text())
    cameras,images,points=read_model(RUN/'dataset/sparse/0')
    rng=np.random.default_rng(20261031)
    origins=[];targets=[];names=[];pids=[];pixels=[];reprojs=[];track_lengths=[]
    for im in sorted(images.values(),key=lambda im:im['name']):
        camera=cameras[im['camera_id']];rotation=qvec_to_rotmat(im['qvec']);center=-rotation.T@im['tvec']
        candidates=[(i,int(pid)) for i,pid in enumerate(im['point3D_ids']) if int(pid) in points and points[int(pid)]['track_len']>=5]
        if not candidates:continue
        obs=np.array([im['points2D_xy'][i] for i,pid in candidates]);xyz=np.array([points[pid]['xyz'] for i,pid in candidates]);pc=xyz@rotation.T+im['tvec']
        predicted,valid=Fisheye(camera).project(pc);errors=np.linalg.norm(predicted-obs,axis=1)
        theta=np.degrees(np.arctan2(np.linalg.norm(pc[:,:2],axis=1),pc[:,2]))
        mask=cv2.imread(str(RUN/'dataset/masks'/Path(im['name']).with_suffix('.png')),0)
        xy=np.rint(obs).astype(int);bounds=(xy[:,0]>=0)&(xy[:,0]<camera['width'])&(xy[:,1]>=0)&(xy[:,1]<camera['height'])
        keep=valid&bounds&(errors<=2)&(theta<=85)
        ix=np.flatnonzero(keep);ix=ix[mask[xy[ix,1],xy[ix,0]]>127]
        if len(ix)>20:ix=rng.choice(ix,20,replace=False)
        for j in sorted(ix):
            origins.append(center);targets.append(xyz[j]);names.append(im['name']);pids.append(candidates[j][1]);pixels.append(obs[j]);reprojs.append(errors[j]);track_lengths.append(points[candidates[j][1]]['track_len'])
    data={'origins':np.array(origins),'targets':np.array(targets),'names':np.array(names),'point_ids':np.array(pids),'image_xy':np.array(pixels),'reprojection_px':np.array(reprojs),'track_lengths':np.array(track_lengths)}
    np.savez_compressed(cache,**data)
    descriptor={'observations':len(names),'images':len(set(names)),'sample_seed':20261031,'per_image_cap':20,'minimum_track_length':5,'maximum_reprojection_pixels':2,'maximum_fisheye_theta_degrees':85,'source_masks_required':True,'model':str(RUN/'dataset/sparse/0'),'cache_sha256':hashlib.sha256(cache.read_bytes()).hexdigest(),'note':'Identical observations reused for baseline and candidates. These points participated in SfM/training; this is consistency, not held-out geometry accuracy.'}
    save(meta,descriptor);return data,descriptor

def topology(mesh):
    start=time.monotonic();vertices=np.asarray(mesh.vertices);faces=np.asarray(mesh.faces)
    # UV/normal splits can create many index components at identical positions.
    rounded=np.round(vertices/1e-5).astype(np.int64)
    _,inverse=np.unique(rounded,axis=0,return_inverse=True);welded=inverse[faces];n=int(inverse.max())+1
    a=welded[:,[0,1,2]].ravel();b=welded[:,[1,2,0]].ravel()
    graph=coo_matrix((np.ones(len(a),np.uint8),(a,b)),shape=(n,n)).tocsr()
    count,labels=connected_components(graph,directed=False,return_labels=True)
    area=np.asarray(mesh.area_faces);face_labels=labels[welded[:,0]]
    face_counts=np.bincount(face_labels,minlength=count);area_counts=np.bincount(face_labels,weights=area,minlength=count)
    order=np.argsort(-area_counts)
    floor=json.loads((HERE.parent/'osmo-format-20261031/sfm-independent-audit.json').read_text())['normalized_main']['floor']
    normal=np.array(floor['normal']);center=np.array(floor['plane_center']);centroids=np.asarray(mesh.triangles_center)
    distance=(centroids-center)@normal;below=distance<-.10
    result={'vertices':len(vertices),'faces':len(faces),'world_bounds':mesh.bounds.tolist(),'surface_area_world_units_squared':float(area.sum()),'weld_precision_world_units':1e-5,'position_welded_vertices':n,'position_welded_components':int(count),'largest_components_by_area':[{'faces':int(face_counts[i]),'area':float(area_counts[i]),'area_fraction':float(area_counts[i]/area.sum())} for i in order[:12]],'components_under_50_faces':int((face_counts<50).sum()),'area_fraction_in_components_under_50_faces':float(area_counts[face_counts<50].sum()/area.sum()),'floor_reference':floor,'area_below_floor_by_0_10_world_units':float(area[below].sum()),'area_fraction_below_floor_by_0_10_world_units':float(area[below].sum()/area.sum()),'elapsed_seconds':time.monotonic()-start}
    print('Topology complete',json.dumps({k:result[k] for k in ('faces','position_welded_components','area_fraction_in_components_under_50_faces','area_fraction_below_floor_by_0_10_world_units')}),flush=True)
    return result

def visibility(mesh,rays,absolute_tolerance=.05,relative_tolerance=.025):
    start=time.monotonic();origins=rays['origins'];vector=rays['targets']-origins;expected=np.linalg.norm(vector,axis=1);directions=vector/expected[:,None]
    distances=np.full(len(expected),np.inf)
    from trimesh.ray.ray_pyembree import RayMeshIntersector
    intersector=RayMeshIntersector(mesh)
    for first in range(0,len(expected),64):
        last=min(first+64,len(expected));locations,ray_ids,_=intersector.intersects_location(origins[first:last],directions[first:last],multiple_hits=False)
        if len(locations):distances[first+ray_ids]=np.linalg.norm(locations-origins[first+ray_ids],axis=1)
        if first%512==0:print('Ray tests',last,'/',len(expected),flush=True)
    tolerance=np.maximum(absolute_tolerance,relative_tolerance*expected)
    error=distances-expected;hit=np.isfinite(distances)
    close=hit&(np.abs(error)<=tolerance);occluding=hit&(error<-tolerance);behind=hit&(error>tolerance);missing=~hit
    result={'observations':len(expected),'near_surface_consistent':int(close.sum()),'early_surface_occludes_observed_feature':int(occluding.sum()),'first_surface_behind_observed_feature':int(behind.sum()),'no_mesh_intersection':int(missing.sum()),'absolute_tolerance_world_units':absolute_tolerance,'relative_tolerance':relative_tolerance,'near_surface_consistent_fraction':float(close.mean()),'early_occlusion_fraction':float(occluding.mean()),'behind_fraction':float(behind.mean()),'no_hit_fraction':float(missing.mean()),'median_absolute_hit_range_error':float(np.median(np.abs(error[hit]))) if hit.any() else None,'p90_absolute_hit_range_error':float(np.percentile(np.abs(error[hit]),90)) if hit.any() else None,'median_early_occlusion_distance':float(np.median(-error[occluding])) if occluding.any() else None,'per_image':[],'elapsed_seconds':time.monotonic()-start}
    for name in sorted(set(rays['names'])):
        ix=rays['names']==name
        result['per_image'].append({'name':str(name),'count':int(ix.sum()),'near_fraction':float(close[ix].mean()),'early_occlusion_fraction':float(occluding[ix].mean()),'behind_fraction':float(behind[ix].mean()),'no_hit_fraction':float(missing[ix].mean())})
    return result,{'expected_range':expected,'first_hit_range':distances,'range_error':error,'tolerance':tolerance,'near':close,'early':occluding,'behind':behind,'missing':missing}

def main():
    p=argparse.ArgumentParser();p.add_argument('--mesh',required=True);p.add_argument('--label',required=True);p.add_argument('--out',required=True);p.add_argument('--skip-topology',action='store_true');args=p.parse_args()
    mesh_path=Path(args.mesh).resolve();output=Path(args.out).resolve()
    if not output.is_relative_to(HERE) or not output.name.startswith('qa-'):raise ValueError('Output must be qa-* under this tool folder')
    print('Loading CPU mesh',str(mesh_path),flush=True);start=time.monotonic()
    scene=trimesh.load_scene(mesh_path,process=False);mesh=scene.to_geometry()
    if not isinstance(mesh,trimesh.Trimesh):raise ValueError('Expected triangle mesh scene')
    result={'label':args.label,'mesh':str(mesh_path),'mesh_sha256':hashlib.sha256(mesh_path.read_bytes()).hexdigest(),'method':'CPU ray consistency at stable masked main-component SfM observations, plus position-welded topology. In-sample geometric consistency only, not external ground truth. World scale is approximate.','trimesh_version':trimesh.__version__,'topology':None}
    if not args.skip_topology:result['topology']=topology(mesh)
    rays,descriptor=fixed_rays();result['ray_sample']=descriptor
    result['visibility'],details=visibility(mesh,rays)
    np.savez_compressed(output.with_suffix('.npz'),**details)
    result['elapsed_seconds']=time.monotonic()-start;save(output,result)
    print(json.dumps({k:v for k,v in result.items() if k not in ('topology',)} if args.skip_topology else {'label':args.label,'topology':result['topology'],'visibility':{k:v for k,v in result['visibility'].items() if k!='per_image'},'elapsed_seconds':result['elapsed_seconds']},indent=2),flush=True)
if __name__=='__main__':main()
