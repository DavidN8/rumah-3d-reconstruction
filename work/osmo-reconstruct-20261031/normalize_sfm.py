from pathlib import Path
import argparse, json
import numpy as np
from seed_fisheye import read_model, write_model_text, qvec_to_rotmat, rotmat_to_qvec

ROOT=Path(r'C:\Users\bombe\OneDrive\Documents\ChatGPT\Ruang Kamare\roomscan-reconstruction\data\20261031_OSMO360\lite-v1')
parser=argparse.ArgumentParser();parser.add_argument('--apply',action='store_true');args=parser.parse_args()
components=[]
for path in sorted((ROOT/'sfm-calibrated-v2/sparse').iterdir()):
    if not path.is_dir():continue
    cams,images,points=read_model(path)
    centers=np.array([-qvec_to_rotmat(im['qvec']).T@im['tvec'] for im in images.values()])
    pp=np.array([p['xyz'] for p in points.values()])
    components.append({'path':str(path),'registered':len(images),'points':len(points),
        'stored_point_error_mean':float(np.mean([p['error'] for p in points.values()])),
        'point_error_note':'Native export stores zero in point error fields. Use SfM log or measured track residuals for reprojection accuracy.',
        'camera_bounds':[centers.min(0).tolist(),centers.max(0).tolist()],
        'camera_median':np.median(centers,axis=0).tolist(),
        'point_percentiles':np.percentile(pp,[1,10,50,90,99],axis=0).tolist(),
        'camera_calibrations':[{k:(v.tolist() if isinstance(v,np.ndarray) else v) for k,v in c.items()} for c in cams.values()]})
print(json.dumps(components,indent=2));(ROOT/'analysis/sfm-inspection.json').write_text(json.dumps(components,indent=2))
if not args.apply:raise SystemExit()
best=max(components,key=lambda c:c['registered'])
if best['registered']<200:raise RuntimeError('Less than 200/260 registered frames: inspect coverage before training.')
cams,images,points=read_model(best['path'])
centers=np.array([-qvec_to_rotmat(im['qvec']).T@im['tvec'] for im in images.values()])
# The native SfM ground-level option writes a single Z-up ground frame.
height=float(np.median(centers[:,2]))
if height<=.05:raise RuntimeError('Ground leveling did not yield cameras above Z=0; inspect orientation.')
scale=1.5/height
rotation=np.array([[1.,0,0],[0,0,1],[0,-1,0]])
assert abs(np.linalg.det(rotation)-1)<1e-8
newpoints={pid:{**p,'xyz':scale*rotation@p['xyz']} for pid,p in points.items()}
newimages={}
for iid,im in images.items():
    r=qvec_to_rotmat(im['qvec']);c=-r.T@im['tvec'];rn=r@rotation.T;cn=scale*rotation@c
    newimages[iid]={**im,'qvec':rotmat_to_qvec(rn),'tvec':-rn@cn}
    ids=im['point3D_ids'];valid=[int(p) for p in ids if int(p) in points][:100]
    if valid:
        x=np.array([points[i]['xyz'] for i in valid])@r.T+im['tvec']
        xx=np.array([newpoints[i]['xyz'] for i in valid])@rn.T+newimages[iid]['tvec']
        assert np.max(np.abs(xx/np.linalg.norm(xx,axis=1)[:,None]-x/np.linalg.norm(x,axis=1)[:,None]))<1e-8
write_model_text(ROOT/'dataset/sparse/0',cams,newimages,newpoints)
report={'source':best['path'],'registered':len(newimages),'points':len(newpoints),'rotation':rotation.tolist(),
        'scale':scale,'scale_basis':'Assumed median capture height1.5m above SfM ground; approximate, not measured.',
        'coordinate_frame':'+Y up, approximate metres, one global similarity for both lenses and whole capture',
        'projection_ray_identity_verified':True,'no_temporal_or_room_splitting':True}
(ROOT/'analysis/normalized-frame.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
