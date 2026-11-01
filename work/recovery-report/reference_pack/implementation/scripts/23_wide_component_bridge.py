"""Test spatially distributed doorway constraints; do not promote a weak fit."""
import json,os,time,shutil
from pathlib import Path
import cv2,numpy as np,torch
import kornia.feature as KF
from scipy.optimize import least_squares
from scipy.spatial.transform import Rotation
from colmap_io import read_model,qvec_to_rotmat
from importlib.machinery import SourceFileLoader
core=SourceFileLoader('recovery_core',str(Path(__file__).with_name('20_component_recovery.py'))).load_module()
BASE,RUN=core.BASE,core.RUN
torch.set_num_threads(16)

def main():
    assert torch.cuda.is_available()
    if (RUN/'analysis/wide-bridge.json').exists():shutil.copy2(RUN/'analysis/wide-bridge.json',RUN/'analysis/wide-bridge-preliminary-512.json')
    models=[read_model(BASE/f'colmap-gpu/ws/sparse/{z}') for z in (0,1)]
    tf=json.loads((RUN/'analysis/component-transforms.json').read_text(encoding='utf-8'))['components']
    images=[{core.srcnum(v['name']):v for v in m[1].values()} for m in models]
    poses={p['name']:p for p in json.loads((RUN/'analysis/all-source-poses.json').read_text(encoding='utf-8'))}
    weights=torch.load(BASE/'analysis/models/loftr_indoor_ds_new.ckpt',map_location='cpu',weights_only=False)
    matcher=KF.LoFTR(pretrained=None);matcher.load_state_dict(weights['state_dict']);matcher=matcher.eval().cuda()
    # Wide window tests plus the actual narrow overlap. Each pair is unique.
    pairs=[(1254,1398),(1281,1412),(1290,1422),(1303,1450),(1316,1461),(1334,1480),(1351,1504),(1363,1530)]
    pairs += [(a,b) for a in [1354,1363,1374,1377,1382,1386] for b in [1390,1398,1406,1412]]
    tensors={};depth_cache={};records=[];allmatches=[]
    def tensor(z,n):
        key=(z,n)
        if key not in tensors:
            a=cv2.imread(str(BASE/'frames'/images[z][n]['name']),0);a=cv2.resize(a,(384,680),interpolation=cv2.INTER_AREA)
            tensors[key]=torch.from_numpy(a).float()[None,None].cuda()/255.
        return tensors[key]
    def camera(z,n):
        im=images[z][n];cam=models[z][0][im['camera_id']];p=cam['params'];K=np.array([[p[0],0,p[2]],[0,p[1],p[3]],[0,0,1.]])
        return im,cam,K
    def depth(z,n):
        if (z,n) in depth_cache:return depth_cache[z,n]
        im,cam,K=camera(z,n);raw=cv2.imread(str(RUN/'geometry-input/depths'/(Path(im['name']).stem+'.png')),-1).astype(np.float32)*.001
        ids=im['point3D_ids'];uv=im['points2D_xy'];keep=ids>=0;ids=ids[keep];uv=uv[keep]
        pp=np.array([models[z][2][int(pid)]['xyz'] for pid in ids]);zz=(pp@qvec_to_rotmat(im['qvec']).T+im['tvec'])[:,2]*tf[z]['scale']
        sampled=cv2.remap(raw,(uv[:,0]*raw.shape[1]/cam['width']).astype(np.float32).reshape(-1,1),(uv[:,1]*raw.shape[0]/cam['height']).astype(np.float32).reshape(-1,1),cv2.INTER_LINEAR).ravel()
        good=(zz>.15)&(sampled>.15)&(sampled<12)&(zz<12)
        if good.sum()<8:return None
        ratios=zz[good]/sampled[good];med=np.median(ratios);mad=np.median(np.abs(ratios-med));vals=ratios[np.abs(ratios-med)<max(.15*med,2.5*mad)]
        if not len(vals):return None
        d=raw*float(np.median(vals));depth_cache[z,n]=d;return d
    def back(z,n,uv):
        if len(uv)==0:return np.empty((0,3))
        im,cam,K=camera(z,n);d=depth(z,n)
        if d is None:return None
        dm=cv2.remap(d,(uv[:,0]*d.shape[1]/cam['width']).astype(np.float32).reshape(-1,1),(uv[:,1]*d.shape[0]/cam['height']).astype(np.float32).reshape(-1,1),cv2.INTER_LINEAR).ravel()
        xy=cv2.undistortPoints(uv.reshape(-1,1,2),K,np.array(cam['params'][4:8])).reshape(-1,2);xc=np.c_[xy,np.ones(len(xy))]*dm[:,None]
        po=poses[im['name']];return (xc-np.array(po['t']))@np.array(po['R'])
    def normal(z,n,uv):
        offsets=np.array([[x,y] for x in [-12,0,12] for y in [-12,0,12]])
        p=back(z,n,uv[None]+offsets)
        if p is None:return np.full(3,np.nan)
        _,_,v=np.linalg.svd(p-p.mean(0));return v[-1]
    for a,b in pairs:
        if a not in images[0] or b not in images[1]:continue
        if depth(0,a) is None or depth(1,b) is None:continue
        with torch.inference_mode():pred=matcher({'image0':tensor(0,a),'image1':tensor(1,b)})
        ua,ub=[pred[k].cpu().numpy()*[1080/384,1920/680] for k in ['keypoints0','keypoints1']];conf=pred['confidence'].cpu().numpy()
        # Known-pair positive control: 512/.35 rejected all real switch matches.
        # Use the previously calibrated 384/.25 configuration for this wider
        # window, retaining independent spatial/plane-support gates below.
        keep=(conf>.25)&(ua[:,0]>20)&(ua[:,0]<1060)&(ub[:,0]>20)&(ub[:,0]<1060)
        ua,ub,conf=ua[keep],ub[keep],conf[keep]
        if len(ua)>=8:
            # Reject false repeated edges in 2D before learned depth is used.
            F,mask=cv2.findFundamentalMat(ua,ub,cv2.USAC_MAGSAC,2.,.999,10000)
            if mask is not None:
                keep=mask.ravel()>0;ua,ub,conf=ua[keep],ub[keep],conf[keep]
        pa,pb=back(0,a,ua),back(1,b,ub)
        accepted=0
        for u,v,pp,qq,c in zip(ua,ub,pa,pb,conf):
            if np.linalg.norm(pp-qq)>.8:continue
            n=normal(0,a,u)
            group='horizontal' if abs(n[1])>.85 else ('wall-x' if abs(n[0])>abs(n[2]) else 'wall-z') if abs(n[1])<.35 else 'slanted'
            allmatches.append({'a':a,'b':b,'uv0':u.tolist(),'uv1':v.tolist(),'p':pp.tolist(),'q':qq.tolist(),'confidence':float(c),'normal':n.tolist(),'group':group});accepted+=1
        records.append({'a':a,'b':b,'image_matches':len(ua),'within_prior_envelope':accepted});print('bridge',a,b,len(ua),accepted,flush=True)
    report={'pairs':records,'matches':len(allmatches),'precise_registration_verified':False,'promote_component_delta':False,'method':'384x680 GPU LoFTR calibrated against known pair; fundamental-matrix checks, observed-track depth scale, floor-preserving component similarity','positive_control':'bridge-positive-control.json'}
    groups={}
    for group in ['horizontal','wall-x','wall-z']:
        pp=np.array([m['p'] for m in allmatches if m['group']==group]).reshape(-1,3)
        groups[group]={'matches':len(pp),'spatial_span_metres':float(np.linalg.norm(pp.max(0)-pp.min(0))) if len(pp) else 0}
    report['plane_groups']=groups
    if len(allmatches)>=12:
        p=np.array([m['p'] for m in allmatches]);q=np.array([m['q'] for m in allmatches]);held=np.arange(len(p))%5==0
        def unpack(x):return np.exp(x[0]),Rotation.from_rotvec([0,x[1],0]).as_matrix(),np.array([x[2],0,x[3]])
        def residual(x,mask):
            s,r,t=unpack(x);return (s*p[mask]@r.T+t-q[mask]).ravel()
        sol=least_squares(lambda x:residual(x,~held),np.zeros(4),loss='soft_l1',f_scale=.025,bounds=([np.log(.8),-.14,-.4,-.4],[np.log(1.2),.14,.4,.4]),max_nfev=200)
        s,r,t=unpack(sol.x);dist=np.linalg.norm(s*p@r.T+t-q,axis=1)
        report.update(candidate_delta={'scale':float(s),'R':r.tolist(),'t':t.tolist()},residual_median=float(np.median(dist)),residual_p90=float(np.percentile(dist,90)),heldout_median=float(np.median(dist[held])),heldout_p90=float(np.percentile(dist[held],90)))
        report['promote_component_delta']=bool(all(g['matches']>=15 and g['spatial_span_metres']>.35 for g in groups.values()) and report['heldout_median']<.04 and report['heldout_p90']<.10)
    report['interpretation']='Three normal/spatial-support groups and held-out residuals are required to consider a whole-kitchen update. Learned depth is not a surveyed accuracy reference. If this gate fails, retain the previous approximate join and disclose it.'
    core.save(RUN/'analysis/wide-bridge.json',report);core.save(RUN/'analysis/wide-bridge-matches.json',allmatches)
    # Witness image for the strongest pair, without hiding other pair failures.
    if allmatches:
        key=max({(m['a'],m['b']) for m in allmatches},key=lambda k:sum((m['a'],m['b'])==k for m in allmatches));a,b=key
        left=cv2.resize(cv2.imread(str(BASE/'frames'/images[0][a]['name'])),(540,960));right=cv2.resize(cv2.imread(str(BASE/'frames'/images[1][b]['name'])),(540,960));out=np.hstack([left,right])
        for m in allmatches:
            if (m['a'],m['b'])!=key:continue
            u=np.array(m['uv0'])/2;v=np.array(m['uv1'])/2+[540,0];cv2.circle(out,tuple(np.round(u).astype(int)),3,(0,255,0),1);cv2.circle(out,tuple(np.round(v).astype(int)),3,(0,255,0),1)
        cv2.imwrite(str(RUN/'analysis/wide-bridge-witness.jpg'),out)
    print(json.dumps(report,indent=2),flush=True)

if __name__=='__main__':main()
