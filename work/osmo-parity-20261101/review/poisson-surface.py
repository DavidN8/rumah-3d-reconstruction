"""Screened Poisson pilot from oriented validated depth and accurate SfM anchors.

This produces an unaccepted local surface, never a deployment. Geometry stays
in the audited +Y world frame. Evaluation views do not qualify anchor tracks.
"""
from pathlib import Path
import sys,json,time,hashlib
import numpy as np
W=Path(__file__).resolve().parent; ROOT=W.parent.parent
sys.path[:0]=[str(W.parent/'tsdfdeps'),str(ROOT/'osmo-improve-20261031/pydeps'),str(ROOT/'osmo-reconstruct-20261031'),str(W.parent)]
from scipy.spatial import cKDTree
import pymeshlab
from seed_fisheye import read_model
from occupied_bounds import ply
CAP=Path('C:/Users/bombe/OneDrive/Documents/ChatGPT/Ruang Kamare/roomscan-reconstruction/data/20261031_OSMO360')
DS=CAP/'clean-v3/explicit-full-v1/dataset'; NATIVE=CAP/'clean-v3/dataset'; OUT=W/'poisson-pilot'; OUT.mkdir(exist_ok=True)
if (OUT/'surface.npz').exists():raise FileExistsError('Preserve existing surface')
started=time.monotonic();bounds=np.asarray(json.loads((W/'occupied-cameras.json').read_text())['bounds']);lo=bounds[0]-.22;hi=bounds[1]+.22
cloud=ply(DS/'seed-dense-train.ply');xyz=np.stack([cloud[n] for n in ['x','y','z']],axis=1);normal=np.stack([cloud[n] for n in ['nx','ny','nz']],axis=1)
length=np.linalg.norm(normal,axis=1);keep=np.isfinite(xyz).all(axis=1)&np.isfinite(normal).all(axis=1)&(length>.5)&np.all((xyz>=lo)&(xyz<=hi),axis=1)
xyz=xyz[keep].astype('f8');normal=normal[keep].astype('f8');normal/=np.linalg.norm(normal,axis=1,keepdims=True)
# Avoid duplicate depth samples overwhelming the more precise feature anchors.
cell=np.floor((xyz-lo)/.008).astype('i4');_,unique=np.unique(cell,axis=0,return_index=True);xyz=xyz[unique];normal=normal[unique]
tree=cKDTree(xyz);_,images,points=read_model(NATIVE/'sparse/0');selection=json.loads((W.parent/'frame-selection.json').read_text())['selected'];train={r['filename']:r['source_frame'] for r in selection if r['split']=='train'}
times={iid:train.get(Path(im['name']).name) for iid,im in images.items()};ids=[];anchors=[]
for pid,p in points.items():
    if p['error']>1.25 or not np.all((p['xyz']>=lo)&(p['xyz']<=hi)):continue
    seen={times[i] for i in p['image_ids'] if times.get(i) is not None}
    if len(seen)<3:continue
    ids.append(pid);anchors.append(p['xyz'])
anchors=np.asarray(anchors);distance,neighbors=tree.query(anchors,k=5,workers=12);n=normal[neighbors];avg=n.mean(axis=1);avg/=np.maximum(np.linalg.norm(avg,axis=1,keepdims=True),1e-12)
stable=(distance[:,0]<.055)&(distance[:,-1]<.085)&(np.min(np.sum(n*avg[:,None,:],axis=2),axis=1)>.80)
anchor_ids=np.asarray(ids)[stable];anchors=anchors[stable];anchor_normals=avg[stable]
positions=np.concatenate([xyz,anchors]);normals=np.concatenate([normal,anchor_normals]);quality=np.r_[np.ones(len(xyz)),np.full(len(anchors),2.0)]
print('Poisson input',len(xyz),'oriented depth samples,',len(anchors),'accurate train-track anchors',flush=True)
orientation={'floorMedianNormalY':float(np.median(normal[xyz[:,1]<.1,1])),'ceilingMedianNormalY':float(np.median(normal[xyz[:,1]>2.3,1]))}
ms=pymeshlab.MeshSet();ms.add_mesh(pymeshlab.Mesh(vertex_matrix=positions,v_normals_matrix=normals,v_scalar_array=quality),'validated-depth-and-train-anchors')
params=dict(depth=9,fulldepth=5,cgdepth=0,scale=1.1,samplespernode=1.5,pointweight=6.0,iters=8,confidence=True,preclean=True,threads=12)
ms.generate_surface_reconstruction_screened_poisson(**params);mesh=ms.current_mesh();v=mesh.vertex_matrix();f=mesh.face_matrix();vn=mesh.vertex_normal_matrix()
# Trim extrapolated exterior only. Do not truncate wall or furniture height.
centers=v[f].mean(axis=1);inside=np.all((centers>=lo)&(centers<=hi),axis=1);f=f[inside];raw_face_count=len(inside)
_,near=tree.query(v,workers=12);alignment=np.sum(vn*normal[near],axis=1);global_flip=np.median(alignment)<0
if global_flip:f=f[:,[0,2,1]];vn=-vn
used,remap=np.unique(f,return_inverse=True);f=remap.reshape(-1,3);v=v[used];vn=vn[used]
np.savez_compressed(OUT/'surface.npz',positions=v.astype('f4'),normals=vn.astype('f4'),faces=f.astype('u4'))
np.savez_compressed(OUT/'input-provenance.npz',anchor_point_ids=anchor_ids,anchor_positions=anchors.astype('f4'))
report={'method':'Screened Poisson, validated oriented depth seed plus accurate native SfM anchors; no Gaussian extraction','dataset':str(DS),'nativeDataset':str(NATIVE),'denseSeedSha256':hashlib.sha256((DS/'seed-dense-train.ply').read_bytes()).hexdigest(),'orientedDepthSamples':len(xyz),'sparseAnchors':len(anchors),'anchorRule':'reprojection error <=1.25 native pixels, >=3 distinct training timestamps; <=.055 distance to dense surface; five-neighbor normal agreement >.80','heldOutDefinition':'Evaluation timestamps excluded from qualifying tracks and texture; SfM itself was solved using all images','qualityWeights':{'dense':1,'sparse':2},'poissonParameters':params,'orientation':orientation,'globalNormalFlip':bool(global_flip),'vertices':len(v),'faces':len(f),'exteriorFacesRemoved':int(raw_face_count-len(f)),'heightCut':False,'worldFrame':'+Y up, original normalized units; no new transform','seconds':time.monotonic()-started,'status':'local pilot, requires visibility carving and visual acceptance'}
(OUT/'poisson-audit.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2),flush=True)
