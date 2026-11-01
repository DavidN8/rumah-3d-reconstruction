"""Read-only screening of large Gaussians against observed training feature rays.

An actually observed static feature supplies empty space before its 3D location.
This tests negative visibility evidence, never distance to a holed mesh or sparse
point support. It does not remove geometry. The projection is a local Gaussian
linearization; any proposed removal still needs before/after render validation.
"""
from pathlib import Path
import argparse,json,sys,time
import numpy as np
from scipy.spatial import cKDTree
from scipy.spatial.transform import Rotation
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent.parent/'osmo-reconstruct-20261031'))
from seed_fisheye import read_model,Fisheye,qvec_to_rotmat
P=argparse.ArgumentParser();P.add_argument('--source',type=Path,required=True);P.add_argument('--output',type=Path,required=True);a=P.parse_args();started=time.monotonic()
DATA=Path('C:/Users/bombe/OneDrive/Documents/ChatGPT/Ruang Kamare/roomscan-reconstruction/data/20261031_OSMO360/clean-v3/dataset')
cameras,images,points=read_model(DATA/'sparse/0')
with a.source.open('rb') as f:
    header=[]
    while (line:=f.readline())!=b'end_header\n':
        if not line:raise ValueError('Invalid PLY')
        header.append(line.decode().strip())
    offset=f.tell()
types={'float':'<f4','float32':'<f4','uchar':'u1'};properties=[line.split() for line in header if line.startswith('property ')]
dtype=np.dtype([(r[2],types[r[1]]) for r in properties]);n=int(next(line.split()[-1] for line in header if line.startswith('element vertex ')))
data=np.memmap(a.source,mode='r',dtype=dtype,offset=offset,shape=(n,))
all_scales=np.exp(np.clip(np.column_stack([data['scale_'+str(i)] for i in range(3)]),-30,30));all_opacity=1/(1+np.exp(-np.clip(data['opacity'],-80,80)))
ids=np.flatnonzero((all_opacity>.1)&(all_scales.max(axis=1)>.05));xyz=np.column_stack([data[k][ids] for k in ['x','y','z']]);scales=all_scales[ids];opacity=all_opacity[ids]
axes=Rotation.from_quat(np.column_stack([data['rot_'+str(i)][ids] for i in [1,2,3,0]])).as_matrix()
training=[im for im in images.values() if im['name'].endswith('_train.jpg')];frame_names=sorted({Path(im['name']).name for im in training});frame_index={name:i for i,name in enumerate(frame_names)}
words=(len(frame_names)+63)//64;negative=np.zeros((len(ids),words),np.uint64);positive=np.zeros_like(negative);view_rows=[]
for number,im in enumerate(training,1):
    valid_obs=[i for i,pid in enumerate(im['point3D_ids']) if int(pid) in points and points[int(pid)]['track_len']>=6 and points[int(pid)]['error']<=1.5]
    if len(valid_obs)<8:continue
    target=np.array([points[int(im['point3D_ids'][i])]['xyz'] for i in valid_obs]);observed=im['points2D_xy'][valid_obs]
    R=qvec_to_rotmat(im['qvec']);model=Fisheye(cameras[im['camera_id']],max_theta_degrees=99)
    target_camera=target@R.T+im['tvec'];target_range=np.linalg.norm(target_camera,axis=1);reprojected,ok=model.project(target_camera);ok&=np.linalg.norm(reprojected-observed,axis=1)<=2
    if ok.sum()<8:continue
    observed=observed[ok];target_range=target_range[ok];tree=cKDTree(observed)
    centre=xyz@R.T+im['tvec'];distance=np.linalg.norm(centre,axis=1);uv,ok=model.project(centre)
    camera=cameras[im['camera_id']];ok&=(uv[:,0]>=0)&(uv[:,0]<camera['width'])&(uv[:,1]>=0)&(uv[:,1]<camera['height'])&(distance>.02)
    ix=np.flatnonzero(ok)
    if not len(ix):continue
    c=centre[ix];d=distance[ix];epsilon=np.maximum(d*1e-5,1e-7);jacobian=np.empty((len(ix),2,3))
    for axis in range(3):
        delta=np.zeros_like(c);delta[:,axis]=epsilon
        plus,_=model.project(c+delta);minus,_=model.project(c-delta);jacobian[:,:,axis]=(plus-minus)/(2*epsilon[:,None])
    basis=np.einsum('ij,njk->nik',R,axes[ix])*scales[ix,None,:]
    A=np.einsum('nij,njk->nik',jacobian,basis);Adepth=np.einsum('ni,nij->nj',c/d[:,None],basis)
    C=np.einsum('nik,njk->nij',A,A)+np.eye(2)[None]*.3;inverse=np.linalg.inv(C)
    cross=np.einsum('nk,nik->ni',Adepth,A);conditional_std=np.sqrt(np.maximum(0,np.sum(Adepth*Adepth,axis=1)-np.einsum('ni,nij,nj->n',cross,inverse,cross)))
    _,neighbours=tree.query(uv[ix],k=8,workers=2);pixel_delta=observed[neighbours]-uv[ix,None,:]
    mahal=np.einsum('nki,nij,nkj->nk',pixel_delta,inverse,pixel_delta);alpha=opacity[ix,None]*np.exp(-.5*mahal)
    ray_mean=d[:,None]+np.einsum('ni,nij,nkj->nk',cross,inverse,pixel_delta)
    target_d=target_range[neighbours];margin=.05*target_d
    intersect=alpha>.1;bad=np.any(intersect&(ray_mean+3*conditional_std[:,None]<target_d-margin),axis=1)
    good=np.any(intersect&(np.abs(ray_mean-target_d)<=margin+3*conditional_std[:,None]),axis=1)
    t=frame_index[Path(im['name']).name];word=t//64;bit=np.uint64(1)<<np.uint64(t%64)
    negative[ix[bad],word]|=bit;positive[ix[good],word]|=bit
    view_rows.append({'name':im['name'],'qualifiedObservedRays':len(observed),'largeGaussianNegativeWitnesses':int(bad.sum()),'largeGaussianPositiveWitnesses':int(good.sum())})
    if number%50==0:print(f'Negative-ray audit {number}/{len(training)} cameras',flush=True)
def popcount(array):return np.unpackbits(array.view(np.uint8).reshape(len(array),-1),axis=1).sum(axis=1)
bad_count=popcount(negative);good_count=popcount(positive);fraction=bad_count/np.maximum(1,bad_count+good_count)
candidate=np.flatnonzero((bad_count>=4)&(fraction>=.8));ranking=sorted(candidate,key=lambda i:int(bad_count[i]),reverse=True)
report={'purpose':__doc__,'source':str(a.source.resolve()),'sourceSplats':n,'screenedLargeSplats':len(ids),'trainTimestamps':len(frame_names),'camerasWithQualifiedRays':len(view_rows),'diagnosticCandidates':len(candidate),'modelEdited':False,'selection':'Source max scale >0.05 normalized units and opacity >0.1. At least four distinct training timestamps supply >80% negative versus positive witness timestamps.','rayQualification':'Masked SfM observations; track length >=6; stored error <=1.5 native pixels; actual reprojection residual <=2 native pixels. Known feature range must exceed the Gaussian conditional mean +3 sigma +5% feature range. No eval timestamps used.','caveats':['Local fisheye Jacobian approximation; not an exact volumetric renderer','Nearest eight observed features per projected centre; a screening test rather than exhaustive ray coverage','No candidates may be deleted without checking the final checkpoint and all source views'],'examples':[{'index':int(ids[i]),'position':xyz[i].tolist(),'scales':scales[i].tolist(),'opacity':float(opacity[i]),'negativeTimestamps':int(bad_count[i]),'positiveTimestamps':int(good_count[i])} for i in ranking[:100]],'views':view_rows,'seconds':time.monotonic()-started}
a.output.write_text(json.dumps(report,indent=2));np.save(a.output.with_suffix('.indices.npy'),ids[candidate]);print(json.dumps({k:v for k,v in report.items() if k not in ['purpose','examples','views']},indent=2))
