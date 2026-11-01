"""Triangulate shared doorway features independently on both sides of the seam.

Tracks use forward/backward optical-flow checks. No depth prediction, walking
speed, or forced equality of the two junction camera centres sets this scale.
"""
import json
from pathlib import Path
import cv2
import numpy as np
from scipy.optimize import least_squares
from scipy.spatial.transform import Rotation
from colmap_io import read_model, qvec_to_rotmat
from importlib import import_module

BASE=Path(__file__).resolve().parents[1]
umeyama=import_module('13_diagnose_bridge').umeyama


def main():
    models=[read_model(BASE/f'colmap-gpu/ws/sparse/{i}') for i in (0,1)]
    frames={int(p.stem.split('_')[-1]):p for p in (BASE/'frames').glob('*.jpg')}
    ref=1386
    gray=cv2.imread(str(frames[ref]),0)
    uv=cv2.goodFeaturesToTrack(gray,maxCorners=5000,qualityLevel=.0005,minDistance=6,blockSize=5).reshape(-1,2)
    # Supplement native SIFT corners, including weak door-frame corners.
    kp,_=cv2.SIFT_create(5000,contrastThreshold=.003).detectAndCompute(gray,None)
    uv=np.concatenate([uv,np.array([k.pt for k in kp],dtype=np.float32)])
    tracks={ref:uv.copy()}
    for sequence in ([n for n in sorted(frames,reverse=True) if 1250<=n<ref],
                     [n for n in sorted(frames) if ref<n<=1550]):
        previous=gray;current=uv.reshape(-1,1,2).copy();valid=np.ones(len(uv),bool)
        for n in sequence:
            image=cv2.imread(str(frames[n]),0)
            forward,st,err=cv2.calcOpticalFlowPyrLK(previous,image,current,None,winSize=(31,31),maxLevel=5,
                             criteria=(cv2.TERM_CRITERIA_EPS|cv2.TERM_CRITERIA_COUNT,40,.001))
            back,bs,_=cv2.calcOpticalFlowPyrLK(image,previous,forward,None,winSize=(31,31),maxLevel=5,
                             criteria=(cv2.TERM_CRITERIA_EPS|cv2.TERM_CRITERIA_COUNT,40,.001))
            delta=np.linalg.norm(back-current,axis=2).ravel()
            valid &= st.ravel().astype(bool)&bs.ravel().astype(bool)&(delta<.6)&(err.ravel()<24)
            pt=forward.reshape(-1,2)
            valid &= (pt[:,0]>5)&(pt[:,0]<1075)&(pt[:,1]>5)&(pt[:,1]<1915)
            rec=pt.copy();rec[~valid]=np.nan;tracks[n]=rec
            current=forward;previous=image
    print('track survival',[(n,int(np.isfinite(v[:,0]).sum())) for n,v in tracks.items() if n in [1386,1382,1378,1374,1366,1390,1394,1398,1402,1414,1430]],flush=True)
    triangulated=[];obs_records=[]
    for comp,(cameras,images,points) in enumerate(models):
        observations=[];projection=[];centres=[];names=[]
        for im in sorted(images.values(),key=lambda x:x['name']):
            n=int(Path(im['name']).stem.split('_')[-1])
            if n not in tracks:continue
            cam=cameras[im['camera_id']];fx,fy,cx,cy=cam['params'][:4]
            k=np.array([[fx,0,cx],[0,fy,cy],[0,0,1.]])
            xy=cv2.undistortPoints(tracks[n].astype(float).reshape(-1,1,2),k,cam['params'][4:8]).reshape(-1,2)
            r=qvec_to_rotmat(im['qvec']);t=im['tvec'];projection.append(np.c_[r,t]);centres.append(-r.T@t)
            observations.append(xy);names.append(n)
        projection=np.array(projection);observations=np.array(observations);centres=np.array(centres)
        xyz=np.full((len(uv),3),np.nan); errors=np.full(len(uv),np.inf);angles=np.zeros(len(uv))
        diagnostics=[]
        for j in range(len(uv)):
            valid=np.isfinite(observations[:,j,0]);xy=observations[valid,j];proj=projection[valid]
            if len(xy)<5:continue
            a=np.stack([xy[:,0,None]*proj[:,2]-proj[:,0],xy[:,1,None]*proj[:,2]-proj[:,1]],axis=1).reshape(-1,4)
            _,_,vt=np.linalg.svd(a,full_matrices=False);x=vt[-1,:3]/vt[-1,3]
            xc=np.einsum('nij,j->ni',proj[:,:,:3],x)+proj[:,:,3]
            if np.any(xc[:,2]<.005):continue
            e=np.linalg.norm(xc[:,:2]/xc[:,2,None]-xy,axis=1)*875
            diagnostics.append((len(xy),float(np.median(e)),float(np.percentile(e,90))))
            if np.percentile(e,90)>3:continue
            rays=x-centres[valid];rays/=np.linalg.norm(rays,axis=1)[:,None]
            angle=np.arccos(np.clip(rays[0]@rays[-1],-1,1))*180/np.pi
            if angle<.3:continue
            xyz[j]=x;errors[j]=np.median(e);angles[j]=angle
        print('triangulation diagnostics',comp,diagnostics[:10],flush=True)
        triangulated.append(xyz);obs_records.append((projection,observations,names))
        print('independently triangulated',comp,np.isfinite(xyz[:,0]).sum(),flush=True)
    valid=np.isfinite(triangulated[0][:,0])&np.isfinite(triangulated[1][:,0])
    src,dst=triangulated[0][valid],triangulated[1][valid]
    print('shared tracks',len(src),flush=True)
    np.savez_compressed(BASE/'analysis/bridge-triangulated.npz',src=src,dst=dst,uv=uv[valid])
    if len(src)<6:raise RuntimeError('not enough independently triangulated cross-seam tracks')
    rng=np.random.default_rng(44);best=None
    for _ in range(10000):
        idx=rng.choice(len(src),4,replace=False);s,r,t=umeyama(src[idx],dst[idx])
        if not .1<s<3:continue
        distance=np.linalg.norm(s*src@r.T+t-dst,axis=1);keep=distance<.015
        if best is None or keep.sum()>best[0]:best=keep.sum(),s,r,t,keep
    _,s,r,t,keep=best
    for _ in range(5):
        s,r,t=umeyama(src[keep],dst[keep]);distance=np.linalg.norm(s*src@r.T+t-dst,axis=1);keep=distance<.015
    # Refine using the actual shared pixel observations, with 3D points as nuisance variables.
    valid_ids=np.flatnonzero(valid)[keep]
    x0=np.r_[Rotation.from_matrix(r).as_rotvec(),np.log(s),t,triangulated[0][valid_ids].ravel()]
    def residual(x):
        rr=Rotation.from_rotvec(x[:3]).as_matrix();ss=np.exp(x[3]);tt=x[4:7];p=x[7:].reshape(-1,3)
        res=[]
        for comp in (0,1):
            pw=p if comp==0 else ss*p@rr.T+tt
            proj,observations,_=obs_records[comp]
            for projection,uvv in zip(proj,observations):
                uvv=uvv[valid_ids];ok=np.isfinite(uvv[:,0]);pc=pw@projection[:,:3].T+projection[:,3]
                pred=pc[:,:2]/np.maximum(pc[:,2,None],.001)
                res.append(((pred[ok]-uvv[ok])*875).ravel())
        return np.concatenate(res)
    # The 3D consensus is already informative; keep BA bounded for weak parallax.
    initial=np.abs(residual(x0));print('reprojection median px',np.median(initial),flush=True)
    out={'method':'forward/backward feature tracks triangulated independently in both SfM components; Sim3 RANSAC',
         'shared_tracks':len(src),'inliers':int(keep.sum()),'scale':float(s),'R':r.tolist(),'t':t.tolist(),
         'median_residual_units':float(np.median(distance[keep])), 'initial_reprojection_median_px':float(np.median(initial)),
         'det':float(np.linalg.det(r))}
    (BASE/'analysis/bridge-triangulated-fit.json').write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=2))


if __name__=='__main__':main()
