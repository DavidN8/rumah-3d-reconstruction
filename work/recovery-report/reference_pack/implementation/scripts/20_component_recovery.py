"""Isolated component-aligned recovery. Never overwrite legacy datasets/checkpoints."""
import argparse, hashlib, json, os, shutil, subprocess, time
from pathlib import Path
import cv2
import numpy as np
from PIL import Image,ImageDraw,ImageFont
from scipy.spatial.transform import Rotation
from colmap_io import read_model,qvec_to_rotmat
from importlib import import_module

BASE=Path(__file__).resolve().parents[1]
RUN=BASE/'recovery-v2'
SPIRULA=BASE.parent/'20261019_095800/runtime/spirula/bin/spirula.exe'
PYTHON=BASE.parent/'20261019_095800/runtime/host-model-venv/Scripts/python.exe'

def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
    return h.hexdigest()

def save(p,d):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    tmp=p.with_suffix(p.suffix+'.tmp');tmp.write_text(json.dumps(d,indent=2),encoding='utf-8');tmp.replace(p)

def srcnum(name):return int(Path(name).stem.split('_')[-1])

def link(src,dst):
    dst=Path(dst);dst.parent.mkdir(parents=True,exist_ok=True)
    if dst.exists():return
    try:os.link(src,dst)
    except OSError:shutil.copy2(src,dst)

def write_model(dest,cams,images,points):
    dest=Path(dest);dest.mkdir(parents=True,exist_ok=True)
    cr=[]
    for cid,cam in cams.items():
        cr.append(f"{cid} {cam['model']} {cam['width']} {cam['height']} "+' '.join(f'{v:.17g}' for v in cam['params']))
    ir=[]
    for iid,im in images.items():
        ir.append(f"{iid} "+' '.join(f'{v:.17g}' for v in im['qvec'])+' '+' '.join(f'{v:.17g}' for v in im['tvec'])+f" {im['camera_id']} {im['name']}")
        xy=im.get('points2D_xy',np.empty((0,2)));ids=im.get('point3D_ids',np.empty(0,dtype=int))
        ir.append(' '.join(f'{u:.9g} {v:.9g} {int(pid) if int(pid) in points else -1}' for (u,v),pid in zip(xy,ids)))
    tracks_by_point={pid:[] for pid in points}
    for iid,im in images.items():
        for idx,pid in enumerate(im.get('point3D_ids',[])):
            if int(pid) in tracks_by_point:tracks_by_point[int(pid)].append(f'{iid} {idx}')
    pr=[]
    for pid,pt in points.items():
        tracks=tracks_by_point[pid]
        pr.append(f"{pid} "+' '.join(f'{v:.17g}' for v in pt['xyz'])+' '+' '.join(str(int(v)) for v in pt['rgb'])+f" {pt.get('error',0):.9g} "+' '.join(tracks))
    (dest/'cameras.txt').write_text('\n'.join(cr)+'\n',encoding='utf-8')
    (dest/'images.txt').write_text('\n'.join(ir)+'\n',encoding='utf-8')
    (dest/'points3D.txt').write_text('\n'.join(pr)+'\n',encoding='utf-8')

def bootstrap():
    for d in ['analysis','datasets','training','exports','logs','review']:(RUN/d).mkdir(parents=True,exist_ok=True)
    backup=BASE/'backups/before-component-rebuild-20261027'
    if not (backup/'manifest.json').exists():
        paths=['exports/iphone-full-room.glb','exports/merge-report.json','review/index.html','review/mesh-viewer.html','review/iPhone-Full-Room-preview.html','review/cameras.json','review/viewer.bundle.js','review/README.txt','viewer-src/room-viewer.js','analysis/fixed-transforms.json','analysis/fixed-verification.json','analysis/fixed-rebuild-check.json']
        paths += [str(p.relative_to(BASE)).replace('\\','/') for p in (BASE/'colmap-gpu/merged/sparse/0').glob('*') if p.is_file()]
        rows=[]
        for rel in paths:
            p=BASE/rel
            if not p.exists():continue
            out=backup/rel;out.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,out)
            assert sha(p)==sha(out)
            rows.append({'path':rel,'bytes':p.stat().st_size,'sha256':sha(out)})
        save(backup/'manifest.json',rows)
    mandate=Path(r'C:/Users/bombe/.codex/attachments/378bdf90-ee05-4182-9cc3-4465ada41139/Pasted text.txt')
    shutil.copy2(mandate,RUN/'architect-mandate.txt')
    models=[read_model(BASE/f'colmap-gpu/ws/sparse/{z}') for z in (0,1)]
    summary=[]
    for z,(cams,ims,pts) in enumerate(models):
        summary.append({'component':z,'cameras':len(ims),'points':len(pts),'camera_models':{str(k):{'model':v['model'],'width':v['width'],'height':v['height'],'params':v['params'].tolist()} for k,v in cams.items()}})
    save(RUN/'analysis/original-components.json',summary)
    fonts=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',17)
    meta=json.loads((BASE/'analysis/frames-meta.json').read_text(encoding='utf-8'))
    sharp={v['src']:v['sharpness'] for v in meta['kept']}
    allims=[im for _,ims,_ in models for im in ims.values()]
    for label,lo,hi in [('kitchen-door',1250,1550),('bedroom-door',3500,4450)]:
        values=sorted([im for im in allims if lo<=srcnum(im['name'])<=hi],key=lambda im:im['name'])
        rows=[]
        for start in range(0,len(values),20):
            subset=values[start:start+20];sheet=Image.new('RGB',(1000,4*395),(26,33,40));draw=ImageDraw.Draw(sheet)
            for k,im in enumerate(subset):
                n=srcnum(im['name']);a=Image.open(BASE/'frames'/im['name']).convert('RGB');a.thumbnail((194,345))
                x=(k%5)*200;y=(k//5)*395
                sheet.paste(a,(x+(200-a.width)//2,y+24));draw.text((x+5,y+3),f'{n} / {n/29.97003:.2f}s',font=fonts,fill='white')
                draw.text((x+4,y+369),f'sharp {sharp.get(n,0):.1f}',font=fonts,fill='white')
                rows.append({'name':im['name'],'frame':n,'sharpness':sharp.get(n)})
            sheet.save(RUN/f'analysis/{label}-{start//20+1:02d}.jpg',quality=94)
        save(RUN/f'analysis/{label}-registered-frames.json',rows)
    save(RUN/'status.json',{'stage':'auditing_transients_and_inputs','original_components':summary,'current_delivery_preserved':True,'gpu':'RTX5080 unrestricted; 16 CPU threads','not_done':['new training','quality acceptance','promotion']})
    print(json.dumps(summary),flush=True)

def geometry():
    ds=RUN/'geometry-input';cams={};images={}
    for z in (0,1):
        cs,ims,_=read_model(BASE/f'colmap-gpu/ws/sparse/{z}')
        assert len(cs)==1
        cams[z+1]=next(iter(cs.values()))
        for im in ims.values():
            rec={k:v for k,v in im.items() if k not in ['points2D_xy','point3D_ids']};rec['camera_id']=z+1
            images[len(images)+1]=rec
            link(BASE/'frames'/im['name'],ds/'images'/im['name'])
    write_model(ds/'sparse/0',cams,images,{})
    command=[str(SPIRULA),'geometry',str(ds),'--model',str(SPIRULA.parent.parent/'models/moge2-vitl-normal.onnx'),'--depth','--depth-units','mm','--ray-depth','no','--max-size','1064','--num-tokens','3600','--normal-format','png','--device','auto']
    save(RUN/'analysis/metric-inference.json',{'command':command,'images':len(images),'depth_units':'millimetres','ray_depth':False,'stage':'running'})
    t0=time.monotonic()
    with (RUN/'logs/metric-inference.log').open('wb',buffering=0) as log:
        ret=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,cwd=BASE)
    result={'command':command,'images':len(images),'depth_units':'millimetres','ray_depth':False,'exit_code':ret.returncode,'elapsed_seconds':time.monotonic()-t0}
    save(RUN/'analysis/metric-inference.json',result);print(json.dumps(result),flush=True)
    if ret.returncode:raise SystemExit(ret.returncode)

def prepare():
    inference=json.loads((RUN/'analysis/metric-inference.json').read_text(encoding='utf-8'))
    assert inference.get('exit_code')==0,'Fresh metric maps must be completed first'
    # Audited frame exclusions: the specified windows mostly show camera motion,
    # not a door swinging. Do not invent a confirmed moving-door label.
    blur={1366,1368,1370,1374,1377,1378,1382,1386,1390,1391,1394,
          3586,3595,3697,3705,3944,4167,4168,4304,4318,4349,4359}
    heldout={903,999,1398,1612,2402,3606,4297,4400}
    trans=json.loads((BASE/'analysis/fixed-transforms.json').read_text(encoding='utf-8'))
    old=json.loads((BASE/'backups/before-fix-20261027/model-merge.json').read_text(encoding='utf-8'))['similarity']
    a=trans['zones']['zone-0'];b=trans['zones']['zone-1']
    # Compose raw kitchen -> old shared training -> upright. Living/bedroom use
    # precisely ONE similarity; no separate zone-2 correction is permitted.
    kitchen={'scale':a['scale']*old['scale'],'R':(np.array(a['R'])@np.array(old['R'])).tolist(),
             't':(a['scale']*np.array(a['R'])@np.array(old['t'])+np.array(a['t'])).tolist()}
    transforms=[kitchen,{k:b[k] for k in ['scale','R','t']}]
    save(RUN/'analysis/component-transforms.json',{'components':transforms,'component_names':['zone-kitchen','zone-living-bedroom'],
         'one_similarity_per_original_component':True,'independent_precise_bridge_verified':False,
         'note':'Initial kitchen join inherits the approximate current join. Wider bridge evidence is audited separately. No local bedroom tilt.'})
    align=import_module('05_seed_cloud');audit=[];allposes=[];depth_records=[]
    for z,name in enumerate(['zone-kitchen','zone-living-bedroom']):
        cams,ims,pts=read_model(BASE/f'colmap-gpu/ws/sparse/{z}')
        ss=transforms[z]['scale'];rr=np.array(transforms[z]['R']);tt=np.array(transforms[z]['t'])
        assert abs(np.linalg.det(rr)-1)<1e-8
        newpts={pid:{**pt,'xyz':ss*rr@pt['xyz']+tt} for pid,pt in pts.items()}
        ds=RUN/'datasets'/name;kept={};removed=[]
        for iid,im in ims.items():
            ro=qvec_to_rotmat(im['qvec']);co=-ro.T@im['tvec'];rn=ro@rr.T;cn=ss*rr@co+tt;tn=-rn@cn
            quat=Rotation.from_matrix(rn).as_quat();qn=np.r_[quat[3],quat[:3]]
            ni={**im,'qvec':qn,'tvec':tn};num=srcnum(im['name'])
            cam=cams[im['camera_id']]
            allposes.append({'name':im['name'],'component':z,'zone':name,'camera':{'model':cam['model'],'width':cam['width'],'height':cam['height'],'params':cam['params'].tolist()},'R':rn.tolist(),'t':tn.tolist(),'position':cn.tolist(),'qvec':qn.tolist(),'heldout':num in heldout,'excluded_blur':num in blur})
            if num in blur or num in heldout:
                removed.append({'name':im['name'],'reason':'held-out fixed source comparison' if num in heldout else 'audited low-sharpness/motion-blur transition'});continue
            # Validate frame math at real sparse tracks before writing a dataset.
            ids=im['point3D_ids'];ids=ids[ids>=0][:150]
            pp=np.array([pts[int(pid)]['xyz'] for pid in ids]);pn=ss*pp@rr.T+tt
            x=pp@ro.T+im['tvec'];xn=pn@rn.T+tn
            assert np.max(np.abs(xn/xn[:,2,None]-x/x[:,2,None]))<1e-8
            kept[iid]=ni;link(BASE/'frames'/im['name'],ds/'images'/im['name'])
        counts={}
        for im in kept.values():
            for pid in np.unique(im['point3D_ids'][im['point3D_ids']>=0]):counts[int(pid)]=counts.get(int(pid),0)+1
        newpts={pid:pt for pid,pt in newpts.items() if counts.get(pid,0)>=2 and pt.get('error',0)<4.}
        write_model(ds/'sparse/0',cams,kept,newpts)
        cam=next(iter(cams.values()));fx,fy,cx,cy=cam['params'][:4];dist=cam['params'][4:8]
        (ds/'depths').mkdir(exist_ok=True);(ds/'normals').mkdir(exist_ok=True)
        failures=[]
        for im in kept.values():
            stem=Path(im['name']).stem;raw=cv2.imread(str(RUN/'geometry-input/depths'/f'{stem}.png'),-1)
            assert raw is not None and raw.dtype==np.uint16
            dh,dw=raw.shape;kd=[fx*dw/cam['width'],fy*dh/cam['height'],cx*dw/cam['width'],cy*dh/cam['height']]
            ids=np.unique(im['point3D_ids'][im['point3D_ids']>=0]);obs=np.array([newpts[int(pid)]['xyz'] for pid in ids if int(pid) in newpts]).reshape(-1,3)
            fit=align.fit_alignment(raw.astype(float),obs,qvec_to_rotmat(im['qvec']),im['tvec'],kd,dist) if len(obs)>=40 else None
            if fit is None or fit[0]<=0:
                failures.append(im['name'])
                link(RUN/'geometry-input/normals'/f'{stem}.png',ds/'normals'/f'{stem}.png')
                depth_records.append({'zone':name,'name':im['name'],'fit_valid':False,'policy':'Retain RGB and normals; omit unreliable depth supervision and dense seeding for this view.'})
                continue
            alpha,beta,fraction=fit
            depth=alpha*raw.astype(np.float32)+beta
            depth=np.where(raw>0,np.clip(depth,.05,60.),0.)
            cv2.imwrite(str(ds/'depths'/f'{stem}.png'),np.round(depth*1000).astype(np.uint16))
            link(RUN/'geometry-input/normals'/f'{stem}.png',ds/'normals'/f'{stem}.png')
            depth_records.append({'zone':name,'name':im['name'],'metric_input_to_pose_z':{'alpha_metres_per_input_mm':float(alpha),'beta_metres':float(beta),'inlier_fraction':float(fraction)},'grid':[dw,dh],'intrinsics':list(map(float,kd))})
        save(ds/'sfm-cameras.json',{'camera':{'model':cam['model'],'width':cam['width'],'height':cam['height'],'params':cam['params'].tolist()}})
        save(ds/'FRAME.json',{'coordinateSystem':'+Y-up, approximate metres; single similarity for original component','component':z,'raw_component':f'colmap-gpu/ws/sparse/{z}','transform':transforms[z],
              'depth_units':'millimetres','input_depth_is_ray_depth':False,'depth_alignment':'fresh metric MoGe affinely aligned to this frame observed sparse tracks; fitted in depth-grid-matched K','source_rgb_resampling':False,'no_local_bedroom_tilt':True})
        audit.append({'zone':name,'component_images':len(ims),'training_dataset_images':len(kept),'removed':removed,'sparse_points':len(newpts),'depth_frames':len(kept)-len(failures),'normal_and_rgb_only_views':failures,'seed_target_max':150000 if z==0 else 300000})
    save(RUN/'analysis/transient-audit.json',{'audited_windows':[[1250,1550],[3500,4450]],'no_confirmed_active_door_swing_in_registered_contacts':True,
         'interpretation':'The doorway windows chiefly show camera motion; registration has gaps across the largest turn/transition intervals. Exclusions are labelled blur, not confirmed swinging doors. Camera/seed defects remain hypotheses for causation until the pilot is tested.',
         'fixed_views_held_out_from_training':sorted(heldout),'datasets':audit})
    save(RUN/'analysis/all-source-poses.json',allposes);save(RUN/'analysis/depth-alignment.json',depth_records)
    print(json.dumps(audit),flush=True)

def seeds():
    for name,cap in [('zone-kitchen',150000),('zone-living-bedroom',300000)]:
        ds=RUN/'datasets'/name;env=os.environ.copy();env.update(DATASET_DIR=str(ds),SFM_CAMERAS=str(ds/'sfm-cameras.json'),SPARSE_MODEL=str(ds/'sparse/0'),SEED_OUTPUT_PLY=str(ds/'seed.ply'),SEED_OUTPUT_JSON=str(RUN/f'analysis/{name}-seed.json'),SEED_MAX_POINTS=str(cap),SEED_VOXEL_DIVISOR='500',SEED_DEPTH_CONVENTION='explicit millimetre z-depth, aligned to observed SfM tracks in approximate metric component frame')
        command=[str(PYTHON),str(BASE/'scripts/05_seed_cloud.py')];start=time.monotonic()
        with (RUN/f'logs/{name}-seed.log').open('wb',buffering=0) as log:ret=subprocess.run(command,env=env,stdout=log,stderr=subprocess.STDOUT,cwd=BASE)
        if ret.returncode:raise RuntimeError(f'Seed failure {name}: see recovery log')
        print(name,'seed complete',round(time.monotonic()-start,2),flush=True)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['bootstrap','geometry','prepare','seeds']);a=parser.parse_args()
    os.environ['OMP_NUM_THREADS']='16'
    for k in ['CUDA_VISIBLE_DEVICES','GPU_DUTY_CYCLE','SS_GPU_DUTY_CYCLE']:os.environ.pop(k,None)
    if a.stage=='bootstrap':bootstrap()
    if a.stage=='geometry':geometry()
    if a.stage=='prepare':prepare()
    if a.stage=='seeds':seeds()

if __name__=='__main__':main()
