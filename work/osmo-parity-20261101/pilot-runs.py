"""Matched pilot pair only. Full training requires a separate visual gate."""
from pathlib import Path
import json,os,sys,hashlib,subprocess
import numpy as np
W=Path(__file__).resolve().parent;OLD=W.parent/'osmo-clean-20261031';sys.path.insert(0,str(W.parent/'osmo-reconstruct-20261031'))
from seed_fisheye import read_model,write_model_text
CAP=Path('C:/Users/bombe/OneDrive/Documents/ChatGPT/Ruang Kamare/roomscan-reconstruction/data/20261031_OSMO360');BASE=CAP/'clean-v3/explicit-full-v1/dataset';HIGH=CAP/'parity-20261101/explicit-1600/dataset';RUN=CAP/'parity-20261101/pilots'
meta=json.loads((BASE/'explicit-pinhole-audit.json').read_text());times=sorted({v['sourceFrame'] for v in meta['views'] if v['sourceSplit']=='train'})
selected=set(times[::5]);refs=json.loads((OLD/'review/clean-cameras.json').read_text())['presets']
for p in refs:
    near=sorted(times,key=lambda n:abs(n-p['sourceFrame']))[:5];selected.update(near)
template=json.loads((OLD/'explicit-full-train-job.json').read_text())['command']
def option(command,flag,value):
    if flag in command:command[command.index(flag)+1]=str(value)
    else:command.extend([flag,str(value)])
results=[]
for label,source in [('baseline-1200',BASE),('sharp-1600',HIGH)]:
    root=RUN/label;ds=root/'dataset'
    if not (ds/'pilot-prepared.json').exists():
        if ds.exists():raise FileExistsError(ds)
        ds.mkdir(parents=True);cams,ims,pts=read_model(source/'sparse/0');audit=json.loads((source/'explicit-pinhole-audit.json').read_text());lookup={v['name']:v for v in audit['views']}
        ims={i:im for i,im in ims.items() if lookup[im['name']]['sourceSplit']=='eval' or lookup[im['name']]['sourceFrame'] in selected}
        pts={i:p for i,p in pts.items() if sum(int(v) in ims for v in p['image_ids'])>=2}
        for p in pts.values():
            keep=np.array([int(v) in ims for v in p['image_ids']]);p['image_ids']=p['image_ids'][keep];p['point2D_idxs']=p['point2D_idxs'][keep];p['track_len']=len(p['image_ids'])
        for im in ims.values():
            im['point3D_ids']=np.array([v if int(v) in pts else -1 for v in im['point3D_ids']])
            for folder,ext in [('images','.jpg'),('masks','.png'),('depths-trusted','.png'),('normals-trusted','.png')]:
                src=(source/folder/im['name']).with_suffix(ext)
                if src.is_file():target=(ds/folder/im['name']).with_suffix(ext);target.parent.mkdir(parents=True,exist_ok=True);os.link(src,target)
        write_model_text(ds/'sparse/0',cams,ims,pts);os.link(BASE/'seed-dense-train.ply',ds/'seed-dense-train.ply')
        record={'label':label,'source':str(source),'sourceFrames':sorted(selected),'trainViews':sum('_train' in im['name'] for im in ims.values()),'evalViews':sum('_eval' in im['name'] for im in ims.values()),'sameOriginalTrainOnlyDenseSeed':True,'scope':'Matched living/dining and both bathroom visits; restricted training timeline, all original held-out timestamps retained'}
        (ds/'pilot-prepared.json').write_text(json.dumps(record,indent=2))
    command=template[:]
    for flag,value in {'--data':ds,'--output-dir-prefix':root/'training','--output-dir-name':label,'--num-iterations':8000,'--refine-stop-iter':5600 if label=='baseline-1200' else 6400,'--refine-stop-num-iter':2400 if label=='baseline-1200' else 1600,'--cap-max':1500000,'--seed-pointcloud':ds/'seed-dense-train.ply','--steps-per-save':8000,'--save-full-checkpoint':1}.items():option(command,flag,value)
    if label=='sharp-1600':
        for flag,value in {'--means-lr':.00016,'--means-lr-final':.0000016,'--noise-lr':10,'--noise-lr-final':0,'--normal-reg-weight':.015,'--floater-suppression':'mild','--use-ppisp':1,'--use-bilateral-grid':1,'--use-bilateral-grid-for-geometry':0}.items():option(command,flag,value)
    status=root/'job.json';request=root/'request.json';job={'stage':label,'command':command,'cwd':str(W),'log':str(root/'train.log'),'status':str(status),'provenance':{'coldStart':True,'originalCaptureAndMasksPreserved':True,'matchedTrainingTimestamps':True,'seedIdentical':True,'totalSteps':8000,'cap':1500000,'pilotNotFullRelease':True,'recipeChange':'RGB sampling plus requested optimizer/regularization changes; combined recipe test, not single-factor causal attribution'}}
    request.write_text(json.dumps(job,indent=2))
    if status.exists():
        previous=json.loads(status.read_text())
        if previous.get('status')=='finished' and previous.get('exit_code')==0:results.append({'label':label,'status':'already_finished'});continue
        raise RuntimeError('Existing pilot state must be inspected before retry: '+str(status))
    result=subprocess.run([sys.executable,str(W/'run_logged_job.py'),str(request)])
    if result.returncode:raise RuntimeError(label+' failed; inspect log')
    results.append({'label':label,'status':'finished'})
(W/'pilot-runs.json').write_text(json.dumps({'results':results,'fullRunStarted':False,'deploymentAuthorized':False},indent=2))
