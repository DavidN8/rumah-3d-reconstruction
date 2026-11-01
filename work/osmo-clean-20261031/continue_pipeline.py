"""Continue the authorized rebuild, preserving completed stages across chat interruptions."""
from pathlib import Path
import hashlib, json, os, subprocess, sys, time

W=Path(__file__).resolve().parent
R=Path(r'C:/Users/bombe/OneDrive/Documents/ChatGPT/Ruang Kamare/roomscan-reconstruction/data/20261031_OSMO360/clean-v3')
STATE=R/'analysis/pipeline.json'
state={'pid':os.getpid(),'started_unix':time.time(),'status':'running'}

def update(stage,**extra):
    state.update(stage=stage,updated_unix=time.time(),**extra)
    temporary=STATE.with_suffix('.tmp')
    temporary.write_text(json.dumps(state,indent=2));temporary.replace(STATE)
    print(stage,flush=True)

def read(path):
    try:return json.loads(path.read_text())
    except (FileNotFoundError,json.JSONDecodeError):return None

def wait_stage(stage):
    while True:
        record=read(R/f'analysis/{stage}.json')
        if record and record['status']!='running':
            if record['status']!='finished' or record.get('exit_code')!=0:
                raise RuntimeError(f'{stage} failed; inspect its recorded command and log')
            return record
        time.sleep(5)

def run(stage):
    existing=read(R/f'analysis/{stage}.json')
    if existing:
        wait_stage(stage)
    else:
        subprocess.run([sys.executable,str(W/'run_stage.py'),stage],cwd=W.parent.parent,check=True)

try:
    update('waiting_for_sfm')
    sfm_record=wait_stage('sfm')
    update('preparing_fresh_scene')
    audit_path=W/'geometry/fresh-sfm-preparation-audit.json'
    audit=read(audit_path)
    if not audit or not audit.get('applied'):
        command=[sys.executable,str(W/'geometry/normalize_fresh_sfm.py'),
                 '--sfm-root',str(Path(sfm_record.get('sfm_root',R/'sfm-native'))),
                 '--coverage',str(W/'geometry/room-coverage.json'),
                 '--source-up','z','--unit-camera-height','--apply']
        with (R/'logs/normalization.log').open('wb',buffering=0) as log:
            subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=True,cwd=W.parent.parent)
    audit=read(audit_path)
    if not audit or not audit.get('applied'):
        raise RuntimeError('Fresh scene was not successfully prepared')
    update('generating_normals')
    run('geometry')
    update('waiting_for_scene_review')
    # Internal review evidence, written only after checking the actual trajectory,
    # both bathroom visits, and calibrated source crops. This is not a user prompt.
    review_path=R/'analysis/scene-review.json'
    while True:
        review=read(review_path)
        if review:
            if review.get('status')!='pass':raise RuntimeError('Scene review did not pass')
            if review.get('normalization_audit_sha256')!=hashlib.sha256(audit_path.read_bytes()).hexdigest():
                raise RuntimeError('Scene review belongs to a different normalization audit')
            break
        time.sleep(5)
    update('training_from_step_zero')
    run('train')
    update('training_complete_pending_visual_review',status='finished')
except BaseException as error:
    update('stopped_for_inspection',status='failed',error=str(error))
    raise
