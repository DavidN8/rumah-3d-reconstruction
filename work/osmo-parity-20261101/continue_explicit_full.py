"""Continue the verified explicit-pinhole workflow; stop before visual release QA."""
from pathlib import Path
import hashlib,json,os,subprocess,sys,time
import cv2,numpy as np
W=Path(__file__).resolve().parent;ROOT=Path('C:/Users/bombe/OneDrive/Documents/ChatGPT/Ruang Kamare/roomscan-reconstruction/data/20261031_OSMO360/clean-v3/explicit-full-v1');DS=ROOT/'dataset';STATE=ROOT/'analysis/continuation.json'
if STATE.exists():raise FileExistsError('Continuation already has state; inspect before starting a second owner')
STATE.parent.mkdir(parents=True,exist_ok=True);state={'pid':os.getpid(),'started_unix':time.time(),'status':'running','stage':'waiting_geometry'}
def save(stage=None,**extra):
    if stage:state['stage']=stage
    state.update(extra,updated_unix=time.time());temporary=STATE.with_suffix('.json.partial');temporary.write_text(json.dumps(state,indent=2));temporary.replace(STATE)
def sha(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def run(stage,script,*args):
    save(stage);result=subprocess.run([sys.executable,str(W/script),*map(str,args)],cwd=W)
    if result.returncode:raise RuntimeError(f'{stage} exited {result.returncode}')
save()
try:
    pilot_path=W/'review/bath-pilot-review.json';pilot=json.loads(pilot_path.read_text())
    if pilot['status']!='pilot_passed_for_full_scene_processing' or not pilot['firstVisitAndReturnViewReviewed']:raise ValueError('Bathroom pilot has not passed review')
    deadline=time.monotonic()+3600
    while True:
        geometry=json.loads((ROOT/'analysis/geometry.json').read_text())
        if geometry['status']=='finished' and geometry.get('exit_code')==0:break
        if geometry['status']=='failed':raise RuntimeError('Full geometry inference failed')
        if time.monotonic()>deadline:raise TimeoutError('Geometry stage exceeded one hour; inspect owned process')
        time.sleep(5)
    builder_path=DS/'explicit-pinhole-audit.json';builder=json.loads(builder_path.read_text())
    if builder['sourceInputs']!=452 or len({v['sourceName'] for v in builder['views']})!=452 or builder['subset']!='all':raise ValueError('Full physical-source coverage failed')
    for relative,expected in builder['sha256'].items():
        if sha(DS/relative)!=expected:raise ValueError('Explicit camera/seed input changed: '+relative)
    if len(list((DS/'depths').glob('*.png')))!=builder['virtualViews'] or len(list((DS/'normals').glob('*.png')))!=builder['virtualViews']:raise ValueError('Incomplete raw geometry maps')
    run('scale_only_depth_checks','fit_explicit_depth.py','--dataset',DS)
    scale=json.loads((DS/'depth-scale-audit.json').read_text())
    if scale['acceptedScales']<100:raise ValueError('Too few independently scale-qualified full-scene views')
    run('multi_timestamp_depth_checks','validate_explicit_depth.py','--dataset',DS,'--max-seed','1500000')
    trusted_path=DS/'trusted-depth-and-seed-audit.json';trusted=json.loads(trusted_path.read_text())
    if trusted['trustedDepthFrames']<100 or trusted['finalSeedPoints']<500000 or trusted['evalInputsUsed'] or trusted['offset']!=0:raise ValueError('Full-scene trusted depth/seed gate failed')
    first=sum(r['written'] for r in trusted['frames'] if 540<=r['sourceFrame']<=720);second=sum(r['written'] for r in trusted['frames'] if 1470<=r['sourceFrame']<=1650)
    if min(first,second)<5:raise ValueError('One bathroom visit lacks trusted geometry')
    save('restricting_normal_guidance_to_validated_pixels')
    normal_dir=DS/'normals-trusted'
    if normal_dir.exists():raise FileExistsError(normal_dir)
    normal_dir.mkdir();normal_hashes={}
    for row in trusted['frames']:
        if not row['written']:continue
        name=Path(row['name']).with_suffix('.png');depth=cv2.imread(str(DS/'depths-trusted'/name),cv2.IMREAD_UNCHANGED);normal=cv2.imread(str(DS/'normals'/name),cv2.IMREAD_COLOR)
        if normal is None or depth is None or depth.shape!=normal.shape[:2]:raise ValueError('Trusted depth/normal shape mismatch')
        normal[depth==0]=0;target=normal_dir/name
        if not cv2.imwrite(str(target),normal):raise IOError(target)
        normal_hashes[name.as_posix()]=sha(target)
    (DS/'trusted-normal-manifest.json').write_text(json.dumps({'normalFiles':normal_hashes,'mask':'Only multi-view-consistent depth pixels remain normal-valid; encoded black is invalid','sourceNormalsModified':False},indent=2))
    template=json.loads((W/'explicit-bath-train-job.json').read_text());command=template['command'][:]
    def option(flag,value):
        index=command.index(flag);command[index+1]=str(value)
    for flag,value in {'--data':DS,'--output-dir-prefix':ROOT/'training','--output-dir-name':'osmo-explicit-depth-v1','--num-iterations':50000,'--refine-stop-iter':35000,'--cap-max':3000000,'--seed-pointcloud':DS/'seed-dense-train.ply','--steps-per-save':5000}.items():option(flag,value)
    job={'stage':'explicit-full-cold-depth-rebuild','command':command,'cwd':str(W),'log':str(ROOT/'logs/train.log'),'status':str(ROOT/'analysis/train.json'),'provenance':{'coldStart':True,'oldCheckpointUsed':False,'physicalSourceImages':452,'registeredSourcePairs':226,'virtualTrainViews':builder['trainViews'],'virtualEvalViews':builder['evalViews'],'positiveDepthScaleOnly':True,'depthOffset':0,'depthAndSeedAuditSha256':sha(trusted_path),'seedSha256':trusted['seedSha256'],'explicitCameraAuditSha256':sha(builder_path),'trustedNormalManifestSha256':sha(DS/'trusted-normal-manifest.json'),'pilotReviewSha256':sha(pilot_path),'scope':'Full Osmo capture; same audited fresh +Y-up world coordinates; native Gaussian delivery planned'}}
    job_path=W/'explicit-full-train-job.json';job_path.write_text(json.dumps(job,indent=2))
    run('training_from_step_zero','run_logged_job.py',job_path)
    save('training_complete_pending_visual_review',status='finished',fullCheckpoint=str(ROOT/'training/osmo-explicit-depth-v1/step-000050000.ckpt/splat.ply'),publicDeploymentApproved=False)
except BaseException as error:
    save(status='failed',error=repr(error));raise
