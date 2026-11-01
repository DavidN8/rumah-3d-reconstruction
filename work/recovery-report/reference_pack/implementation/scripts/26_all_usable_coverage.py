"""Correct the extra view holdouts in an isolated, full-coverage living run.

Source-photo comparisons for this derivative are delivery checks, not unseen
generalization tests. The first recovery run remains immutable for ablation.
"""
import json,os,subprocess
from pathlib import Path
from importlib import import_module
from importlib.machinery import SourceFileLoader
import numpy as np
import cv2
from scipy.spatial.transform import Rotation
from colmap_io import read_model,qvec_to_rotmat
core=SourceFileLoader('coverage_core',str(Path(__file__).with_name('20_component_recovery.py'))).load_module()
pilot=SourceFileLoader('coverage_pilot',str(Path(__file__).with_name('21_recovery_pilot.py'))).load_module()
BASE,RUN=core.BASE,core.RUN
NAME='zone-living-bedroom-allviews'

def prepare():
    ds=RUN/'datasets'/NAME
    if ds.exists():raise RuntimeError('Refuse to overwrite the frozen full-coverage dataset')
    rows=json.loads((RUN/'analysis/all-source-poses.json').read_text(encoding='utf-8'))
    valid={r['name'] for r in rows if r['component']==1 and not r['excluded_blur']}
    cams,ims,pts=read_model(BASE/'colmap-gpu/ws/sparse/1')
    tf=json.loads((RUN/'analysis/component-transforms.json').read_text(encoding='utf-8'))['components'][1]
    ss,rr,tt=tf['scale'],np.array(tf['R']),np.array(tf['t'])
    kept={}
    for iid,im in ims.items():
        if im['name'] not in valid:continue
        ro=qvec_to_rotmat(im['qvec']);rn=ro@rr.T;cn=ss*rr@(-ro.T@im['tvec'])+tt;q=Rotation.from_matrix(rn).as_quat()
        kept[iid]={**im,'qvec':np.r_[q[3],q[:3]],'tvec':-rn@cn}
        core.link(BASE/'frames'/im['name'],ds/'images'/im['name'])
    counts={}
    for im in kept.values():
        for pid in np.unique(im['point3D_ids'][im['point3D_ids']>=0]):counts[int(pid)]=counts.get(int(pid),0)+1
    newpts={pid:{**p,'xyz':ss*rr@p['xyz']+tt} for pid,p in pts.items() if counts.get(pid,0)>=2 and p.get('error',0)<4}
    core.write_model(ds/'sparse/0',cams,kept,newpts)
    cam=next(iter(cams.values()));fx,fy,cx,cy=cam['params'][:4];dist=cam['params'][4:8]
    (ds/'depths').mkdir();(ds/'normals').mkdir();align=import_module('05_seed_cloud');records=[]
    for im in kept.values():
        stem=Path(im['name']).stem;raw=cv2.imread(str(RUN/'geometry-input/depths'/f'{stem}.png'),-1);h,w=raw.shape
        kd=[fx*w/cam['width'],fy*h/cam['height'],cx*w/cam['width'],cy*h/cam['height']]
        ids=np.unique(im['point3D_ids'][im['point3D_ids']>=0]);obs=np.array([newpts[int(i)]['xyz'] for i in ids if int(i) in newpts]).reshape(-1,3)
        fit=align.fit_alignment(raw.astype(float),obs,qvec_to_rotmat(im['qvec']),im['tvec'],kd,dist) if len(obs)>=40 else None
        core.link(RUN/'geometry-input/normals'/f'{stem}.png',ds/'normals'/f'{stem}.png')
        rec={'name':im['name'],'depth_fit_valid':fit is not None and fit[0]>0}
        if rec['depth_fit_valid']:
            a,b,f=fit;depth=np.where(raw>0,np.clip(a*raw.astype(np.float32)+b,.05,60),0)
            cv2.imwrite(str(ds/'depths'/f'{stem}.png'),np.round(depth*1000).astype(np.uint16));rec.update(alpha=float(a),beta=float(b),inlier_fraction=float(f))
        records.append(rec)
    core.save(ds/'sfm-cameras.json',{'camera':{'model':cam['model'],'width':cam['width'],'height':cam['height'],'params':cam['params'].tolist()}})
    core.save(ds/'FRAME.json',{'coordinateSystem':'+Y-up approximate metres','component':1,'transform':tf,'depth_units':'millimetres','input_depth_is_ray_depth':False,'no_local_bedroom_tilt':True,'evaluation':'All usable views train. Source comparisons are in-sample delivery checks.'})
    core.save(RUN/'analysis/all-usable-coverage.json',{'dataset':NAME,'usable_images':len(kept),'excluded_blur_images':len(ims)-len(kept),'fixed_comparison_images_in_training':[1398,1612,2402,3606,4297,4400],'eval_mode':'all','previous_dataset_images':305,'previous_interval_eval_images':26,'previous_actual_training_images':279,'depth_fits':records,'purpose':'Test whether restoring endpoint and fixed-view coverage improves the remaining doorway defect; no success assumed.'})
    env=os.environ.copy();env.update(OMP_NUM_THREADS='16',DATASET_DIR=str(ds),SFM_CAMERAS=str(ds/'sfm-cameras.json'),SPARSE_MODEL=str(ds/'sparse/0'),SEED_OUTPUT_PLY=str(ds/'seed.ply'),SEED_OUTPUT_JSON=str(RUN/f'analysis/{NAME}-seed.json'),SEED_MAX_POINTS='300000',SEED_VOXEL_DIVISOR='500',SEED_DEPTH_CONVENTION='explicit millimetre z-depth; matched K and observed SfM tracks')
    with (RUN/f'logs/{NAME}-seed.log').open('wb',buffering=0) as log:subprocess.run([str(core.PYTHON),str(BASE/'scripts/05_seed_cloud.py')],env=env,cwd=BASE,stdout=log,stderr=subprocess.STDOUT,check=True)
    print('Prepared',len(kept),'usable images, all contributing to training.',flush=True)

if __name__=='__main__':
    os.environ['OMP_NUM_THREADS']='16'
    prepare();pilot.train(NAME,eval_mode='all');pilot.mesh(NAME)
