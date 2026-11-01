"""Independent CPU audit of the Osmo main component; no dataset mutations."""
import os
os.environ['OMP_NUM_THREADS']='2'
os.environ['OPENBLAS_NUM_THREADS']='2'
from pathlib import Path
import json,sys,re,math
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'osmo-reconstruct-20261031'))
from seed_fisheye import read_model,qvec_to_rotmat,Fisheye
from PIL import Image,ImageDraw

HERE=Path(__file__).parent
RUN=Path(r'C:\Users\bombe\OneDrive\Documents\ChatGPT\Ruang Kamare\roomscan-reconstruction\data\20261031_OSMO360\lite-v1')
cameras,images,points=read_model(RUN/'dataset/sparse/0')
raw_c,raw_i,raw_p=read_model(RUN/'sfm-calibrated-v2/sparse/0')
secondary_c,secondary_i,secondary_p=read_model(RUN/'sfm-calibrated-v2/sparse/1')
name_to_image={im['name']:im for im in images.values()}
secondary_names={im['name'] for im in secondary_i.values()}
centers={iid:-qvec_to_rotmat(im['qvec']).T@im['tvec'] for iid,im in images.items()}
time=lambda name:(int(re.search(r'(\d+)$',Path(name).stem)[1])-1)/2
frame=lambda name:int(re.search(r'(\d+)$',Path(name).stem)[1])
main_names=set(name_to_image)
unique_secondary=sorted(secondary_names-main_names)
missing=[f'cam{cam}/frame_{f:06d}.jpg' for cam in (0,1) for f in range(1,131) if f'cam{cam}/frame_{f:06d}.jpg' not in main_names]
missing_all=[n for n in missing if n not in secondary_names]

residual_chunks=[];invalid_count=0;obs_count=0;per_image=[]
for iid,im in images.items():
    ix=np.flatnonzero(np.isin(im['point3D_ids'],list(points)))
    if not len(ix):continue
    xyz=np.asarray([points[int(im['point3D_ids'][j])]['xyz'] for j in ix])
    r=qvec_to_rotmat(im['qvec']);xyz=xyz@r.T+im['tvec']
    xy,valid=Fisheye(cameras[im['camera_id']]).project(xyz)
    residual=np.linalg.norm(xy-im['points2D_xy'][ix],axis=1)
    good=valid&np.isfinite(residual)
    residual_chunks.append(residual[good]);obs_count+=len(ix);invalid_count+=int((~good).sum())
    per_image.append({'name':im['name'],'observations':int(good.sum()),'mean_px':float(residual[good].mean()),'p95_px':float(np.percentile(residual[good],95))})
residual=np.concatenate(residual_chunks)
xyz=np.asarray([p['xyz'] for p in points.values()])
floor_candidates=xyz[np.abs(xyz[:,1])<.06]
floor_center=np.median(floor_candidates,axis=0)
u,s,vh=np.linalg.svd(floor_candidates-floor_center,full_matrices=False)
normal=vh[-1];normal*=np.sign(normal[1])
floor_distance=(floor_candidates-floor_center)@normal
keep=np.abs(floor_distance)<.025
center=floor_candidates[keep].mean(0)
_,_,vh=np.linalg.svd(floor_candidates[keep]-center,full_matrices=False)
normal=vh[-1];normal*=np.sign(normal[1])
tilt=math.degrees(math.acos(np.clip(normal[1],-1,1)))

trajectory=[]
for im in sorted([im for im in images.values() if im['name'].startswith('cam0/')],key=lambda im:time(im['name'])):
    trajectory.append({'name':im['name'],'time':time(im['name']),'center':centers[im['id']].tolist()})
dist=np.linalg.norm(np.diff(np.asarray([p['center'] for p in trajectory]),axis=0),axis=1)
dt=np.diff([p['time'] for p in trajectory]);speed=dist/dt

# One similarity aligns shared secondary camera centers to the accepted main.
overlap=sorted(main_names&secondary_names)
sec_by_name={im['name']:im for im in secondary_i.values()}
src=np.asarray([-qvec_to_rotmat(sec_by_name[n]['qvec']).T@sec_by_name[n]['tvec'] for n in overlap])
dst=np.asarray([centers[name_to_image[n]['id']] for n in overlap])
xc=src-src.mean(0);yc=dst-dst.mean(0)
uu,ss,vvt=np.linalg.svd(yc.T@xc/len(src));diag=np.eye(3);diag[-1,-1]=np.linalg.det(uu@vvt)
rotation=uu@diag@vvt;scale=np.trace(np.diag(ss)@diag)/np.mean(np.sum(xc*xc,axis=1))
translation=dst.mean(0)-scale*rotation@src.mean(0)
secondary_residual=np.linalg.norm(scale*(src@rotation.T)+translation-dst,axis=1)
angles=[]
for n in overlap:
    rs=qvec_to_rotmat(sec_by_name[n]['qvec'])@rotation.T
    rd=qvec_to_rotmat(name_to_image[n]['qvec'])
    cos=(np.trace(rd@rs.T)-1)/2
    angles.append(math.degrees(math.acos(np.clip(cos,-1,1))))

norm=json.loads((RUN/'analysis/normalized-frame.json').read_text())
rr=np.array(norm['rotation']);sc=norm['scale']
point_identity=max(np.linalg.norm(points[pid]['xyz']-sc*rr@p['xyz']) for pid,p in raw_p.items())
height=np.array([c[1] for c in centers.values()])
report={'normalized_main':{'images':len(images),'points':len(points),'camera_groups':len(cameras),'time_range_seconds':[min(map(lambda x:time(x['name']),images.values())),max(map(lambda x:time(x['name']),images.values()))],
    'reprojection':{'observations':obs_count,'invalid_projection_observations':invalid_count,'mean_px':float(residual.mean()),'median_px':float(np.median(residual)),'p95_px':float(np.percentile(residual,95)),'p99_px':float(np.percentile(residual,99)),'maximum_px':float(residual.max()),'method':'Recomputed OPENCV_FISHEYE projection of every valid observation, not the zero-valued writer point.error field.'},
    'camera_height_y':{'minimum':float(height.min()),'median':float(np.median(height)),'maximum':float(height.max())},
    'floor':{'candidate_points_near_y0':len(floor_candidates),'refit_inlier_points':int(keep.sum()),'normal':normal.tolist(),'tilt_from_world_up_degrees':tilt,'plane_center':center.tolist(),'interpretation':'Independent least-squares fit of the near-ground sparse support band. Does not establish measured metric scale.'},
    'trajectory':{'camera0_frames':len(trajectory),'distance_total_approx_units':float(dist.sum()),'max_neighbor_step':float(dist.max()),'p95_speed_units_per_second':float(np.percentile(speed,95)),'max_speed_units_per_second':float(speed.max()),'largest_step_to':trajectory[int(np.argmax(dist))+1]['name'],'note':'Units inherit the assumed1.5m camera-height scale. Late low camera positions agree with the rolled/downward raw footage.'},
    'global_similarity_identity_max_point_error':float(point_identity)},
    'secondary':{'images':len(secondary_i),'shared_with_main':len(overlap),'unique_images':unique_secondary,'unique_times_seconds':sorted({time(n) for n in unique_secondary}),'shared_center_similarity_fit_residual_median':float(np.median(secondary_residual)),'shared_center_similarity_fit_residual_p95':float(np.percentile(secondary_residual,95)),'shared_orientation_difference_median_degrees':float(np.median(angles)),'shared_orientation_difference_p95_degrees':float(np.percentile(angles,95)),'warning':'Diagnostic alignment only, never applied. Native rejected its merge; keep isolated rather than invent a seam.'},
    'missing_from_main':missing,'missing_from_every_component':missing_all,'trajectory_camera0':trajectory,
    'per_image_reprojection':per_image}
(HERE/'sfm-independent-audit.json').write_text(json.dumps(report,indent=2))

# Lightweight point/trajectory inspection plot, avoiding another package runtime.
canvas=Image.new('RGB',(1600,900),(20,27,35));draw=ImageDraw.Draw(canvas)
panels=[('Top: X / Z; color = height',0,2,50,70,730,740),('Side: X / Y',0,1,850,70,680,740)]
rng=np.random.default_rng(20261031);sample=xyz[rng.choice(len(xyz),min(40000,len(xyz)),replace=False)]
for title,a,b,x0,y0,w,h in panels:
    bounds=np.percentile(xyz[:,[a,b]],[.5,99.5],axis=0);lo,hi=bounds
    span=hi-lo;factor=min(w/span[0],h/span[1]);cx=x0+w/2;cy=y0+h/2;mid=(hi+lo)/2
    def screen(p):return (int(cx+(p[a]-mid[0])*factor),int(cy-(p[b]-mid[1])*factor))
    draw.text((x0,y0-35),title,fill='white')
    for point in sample:
        x,y=screen(point)
        if x0<=x<x0+w and y0<=y<y0+h:
            t=float(np.clip(point[1]/2.5,0,1));draw.point((x,y),fill=(int(40+170*t),int(160-40*t),int(230-120*t)))
    line=[screen(np.array(p['center'])) for p in trajectory]
    draw.line(line,fill=(255,205,70),width=3)
    for sec in (1,12,20,30,40,55):
        p=min(trajectory,key=lambda p:abs(p['time']-sec));pos=screen(np.array(p['center']))
        draw.ellipse((pos[0]-4,pos[1]-4,pos[0]+4,pos[1]+4),fill=(255,245,220));draw.text((pos[0]+6,pos[1]-10),f"{p['time']:g}s",fill='white')
draw.text((50,840),'Accepted main component only. Camera path = yellow. Scale is approximate; no secondary join applied.',fill=(210,220,230))
canvas.save(HERE/'sfm-point-trajectory.png')
print(json.dumps({k:v for k,v in report.items() if k not in ('trajectory_camera0','per_image_reprojection')},indent=2))
