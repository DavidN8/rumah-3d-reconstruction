"""Projection sanity checks and gated fresh training/extraction for recovery v2."""
import argparse,json,os,subprocess,time,re
from pathlib import Path
import cv2
import numpy as np
from PIL import Image,ImageDraw,ImageFont
from importlib import import_module
from colmap_io import read_model,qvec_to_rotmat
from importlib.machinery import SourceFileLoader
core=SourceFileLoader('component_recovery',str(Path(__file__).with_name('20_component_recovery.py'))).load_module()
BASE,RUN,SPIRULA=core.BASE,core.RUN,core.SPIRULA

def read_seed(path):
    with Path(path).open('rb') as f:
        head=b''
        while b'end_header\n' not in head:head+=f.readline()
        count=int(re.search(rb'element vertex (\d+)',head).group(1))
        d=np.frombuffer(f.read(),dtype=np.dtype([('xyz','<f4',(3,)),('rgb','u1',(3,))]),count=count)
    return d['xyz'].copy(),d['rgb'].copy()

def seed_checks(living_name='zone-living-bedroom'):
    poses={p['name']:p for p in json.loads((RUN/'analysis/all-source-poses.json').read_text(encoding='utf-8'))}
    tag='allviews-' if living_name.endswith('-allviews') else ''
    out=[];pics=[];font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',21)
    for z,name in enumerate(['zone-kitchen',living_name]):
        ds=RUN/'datasets'/name;xyz,rgb=read_seed(ds/'seed.ply');assert np.isfinite(xyz).all()
        report={'zone':name,'points':len(xyz),'bounds':[xyz.min(0).tolist(),xyz.max(0).tolist()],'views':[]}
        for num in ([903,999] if z==0 else [3606,4297]):
            filename=f'frame_{num:07d}.jpg';cam=poses[filename];r=np.array(cam['R']);t=np.array(cam['t']);k=cam['camera']['params'];K=np.array([[k[0],0,k[2]],[0,k[1],k[3]],[0,0,1.]])
            pc=xyz@r.T+t;ok=pc[:,2]>.1;ids=np.flatnonzero(ok)
            uv,_=cv2.projectPoints(pc[ok],np.zeros(3),np.zeros(3),K,np.array(k[4:8]));uv=uv.reshape(-1,2)
            inside=(uv[:,0]>4)&(uv[:,0]<1076)&(uv[:,1]>4)&(uv[:,1]<1916);ids=ids[inside];uv=uv[inside]
            # A coarse z-buffer prevents a farther wall's points painting over
            # a foreground object; this is still a projection sanity check.
            bins=(uv/4).astype(int);key=bins[:,1]*270+bins[:,0]
            order=np.argsort(pc[ids,2]);_,u=np.unique(key[order],return_index=True);visible=order[u]
            rng=np.random.default_rng(num);sel=rng.choice(visible,min(1600,len(visible)),replace=False)
            image=cv2.imread(str(BASE/'frames'/filename));small=cv2.resize(image,(540,960))
            overlay=small.copy()
            for u,v in uv[sel]/2:cv2.circle(overlay,(round(u),round(v)),1,(255,220,0),-1,cv2.LINE_AA)
            overlay=cv2.addWeighted(overlay,.65,small,.35,0)
            canvas=np.full((1000,1080,3),25,np.uint8);canvas[40:1000,:540]=small;canvas[40:1000,540:]=overlay
            cv2.putText(canvas,f'{name} / {num} / source | projected seed',(12,27),cv2.FONT_HERSHEY_SIMPLEX,.65,(240,240,240),1,cv2.LINE_AA)
            path=RUN/f'analysis/{tag}proj-check-{num}.jpg';cv2.imwrite(str(path),canvas,[cv2.IMWRITE_JPEG_QUALITY,95]);pics.append(Image.open(path).copy())
            report['views'].append({'name':filename,'heldout':False if z==1 and tag else cam['heldout'],'projected_in_frame':len(ids),'zbuffer_visible_samples':len(visible),'rendered_samples':len(sel)})
        out.append(report)
    sheet=Image.new('RGB',(2160,2000),(25,25,25))
    for k,im in enumerate(pics):sheet.paste(im,((k%2)*1080,(k//2)*1000))
    sheet.save(RUN/f'analysis/{tag}proj_check.jpg',quality=95)
    core.save(RUN/f'analysis/{tag}seed-projection-check.json',{'datasets':out,'meaning':'Sanity check only; correct projection and same-frame placement do not prove independent surface accuracy.'})
    print(json.dumps(out),flush=True)

def train(name,eval_mode='interval'):
    ds=RUN/'datasets'/name;assert (ds/'seed.ply').exists()
    if name.startswith('zone-living-bedroom'):
        gate=json.loads((RUN/'analysis/kitchen-pilot-gate.json').read_text(encoding='utf-8'))
        assert gate.get('visually_improved') is True,'Living/bedroom training requires a visibly improved kitchen pilot'
    iters=40000 if name=='zone-kitchen' else 50000;cap=2500000 if name=='zone-kitchen' else 3000000
    target=RUN/'training'/name
    if target.exists():raise RuntimeError(f'Training already exists: {target}; use an explicit continuation, do not overwrite')
    cmd=[str(SPIRULA),'train','meshing','--data',str(ds),'--output-dir-prefix',str(RUN/'training'),'--output-dir-name',name,
         '--quality','high','--cap-max',str(cap),'--num-iterations',str(iters),'--refine-stop-iter',str(iters-10000),
         '--train-resolution-divisor','1','--progressive-resolution','1','--progressive-resolution-full-at','0.3',
         '--max-world-size','0.12','--sh-degree','3','--sh-reg','0.001','--distraction-robustness','mild','--floater-suppression','mild',
         '--load-depths','1','--load-normals','1','--input-depth-is-ray-depth','0','--depth-supervision-weight','0.05','--normal-supervision-weight','0.02',
         '--scene-center','none','--train-frame','points','--orientation-method','none','--center-method','none','--auto-scale-poses','0',
         '--eval-mode',eval_mode,'--eval-interval','12','--save-eval-images','1',
         '--seed-pointcloud',str(ds/'seed.ply'),'--steps-per-save','5000','--save-only-latest-checkpoint','0','--save-full-checkpoint','1',
         '--disable-viewer','1','--keep-viewer-alive','0','--device','auto']
    env=os.environ.copy();env['OMP_NUM_THREADS']='16'
    for key in ['CUDA_VISIBLE_DEVICES','GPU_DUTY_CYCLE','SS_GPU_DUTY_CYCLE']:env.pop(key,None)
    record={'zone':name,'command':cmd,'stage':'training','started_unix':time.time(),'legacy_checkpoint_reused':False,'cpu_threads':16,'source_data':str(ds)}
    core.save(RUN/f'analysis/{name}-training.json',record);core.save(RUN/'status.json',record)
    print('Launching fresh',name,flush=True);t0=time.monotonic()
    with (RUN/f'logs/{name}-train.log').open('wb',buffering=0) as log:ret=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,cwd=BASE,env=env)
    record.update(exit_code=ret.returncode,elapsed_seconds=time.monotonic()-t0,stage='training_complete' if ret.returncode==0 else 'training_failed')
    core.save(RUN/f'analysis/{name}-training.json',record);core.save(RUN/'status.json',record);print(json.dumps(record),flush=True)
    if ret.returncode:raise SystemExit(ret.returncode)
    config=json.loads((target/'config.json').read_text(encoding='utf-8'))
    assert config['quality']=='high' and config['depth_unit_scale_factor']==.001 and config['input_depth_is_ray_depth'] is False

def mesh(name):
    dest=RUN/'exports'/name;dest.mkdir(exist_ok=True)
    cmd=[str(SPIRULA),'mesh',str(RUN/'training'/name),'--data',str(RUN/'datasets'/name),
         '--output',str(dest/name),'--format','glb+jpeg90','--color','texture','--texture-size','8192','--num-threads','16',
         '--merge-factor','0.5','--bisection-iters','4','--carve-k','3','--fill-hole-ratio','0','--fill-hole-max-edges','64','--floater-min-faces','50','--device','auto']
    # Intentionally leave acceleration grid at native/default 512 and iso at
    # camera-supported default 0.5, rather than the compact 384 / 1.2 recipe.
    start=time.monotonic();core.save(RUN/f'analysis/{name}-meshing.json',{'command':cmd,'stage':'meshing'})
    with (RUN/f'logs/{name}-mesh.log').open('wb',buffering=0) as log:ret=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,cwd=BASE)
    record={'command':cmd,'exit_code':ret.returncode,'elapsed_seconds':time.monotonic()-start,'mesh':str(dest/(name+'.glb'))}
    core.save(RUN/f'analysis/{name}-meshing.json',record);print(json.dumps(record),flush=True)
    if ret.returncode:raise SystemExit(ret.returncode)

def main():
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['seed-check','train','mesh']);p.add_argument('--zone',default='zone-kitchen',choices=['zone-kitchen','zone-living-bedroom']);a=p.parse_args()
    os.environ['OMP_NUM_THREADS']='16'
    if a.stage=='seed-check':seed_checks()
    elif a.stage=='train':train(a.zone)
    else:mesh(a.zone)

if __name__=='__main__':main()
