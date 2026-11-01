"""One authorized isolated 40000->50000 geometry-prior refinement trial."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

HERE=Path(__file__).resolve().parent
DATA=Path(r'C:\Users\bombe\OneDrive\Documents\ChatGPT\Ruang Kamare\roomscan-reconstruction\data')
SOURCE=DATA/'20261031_OSMO360/lite-v1/training/osmo-lite-trusted-v3'
RUN=DATA/'20261031_OSMO360/recovery-v2'
OUTPUT=RUN/'training/osmo-surface-v4'
RECORD=RUN/'analysis/train-surface-v4.json'
LOG=RUN/'logs/train-surface-v4.log'
FILES=['config.json','scene_transform.json','step-000040000.ckpt/splat.ply','step-000040000.ckpt/state.tar']

def sha(path):
    digest=hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda:handle.read(8*1024*1024),b''):digest.update(chunk)
    return digest.hexdigest()

def save(record):
    RECORD.parent.mkdir(parents=True,exist_ok=True)
    temp=RECORD.with_suffix('.tmp');temp.write_text(json.dumps(record,indent=2));temp.replace(RECORD)

def command():
    return [str(DATA/'20261019_095800/runtime/spirula/bin/spirula.exe'),'train',
        '--resume',str(OUTPUT/'step-000040000.ckpt'),
        '--data',str(DATA/'20261031_OSMO360/lite-v1/dataset'),
        '--output-dir-prefix',str(RUN/'training'),'--output-dir-name','osmo-surface-v4',
        '--num-iterations','50000','--cap-max','3000000',
        '--refine-stop-iter','48000','--refine-stop-num-iter','2000',
        '--max-world-size','.12','--normal-reg-weight','.1',
        '--normal-supervision-weight','.06','--depth-supervision-weight','.1',
        '--sh-degree','0','--depth-dir','depths-trusted-scale',
        '--input-depth-is-ray-depth','1','--warp-to-pinhole','1',
        '--load-masks','1','--mask-dir','masks','--apply-loss-for-mask','0',
        '--auto-scale-poses','0','--train-resolution-divisor','1',
        '--save-only-latest-checkpoint','1','--save-full-checkpoint','1',
        '--save-eval-images','0','--disable-viewer','1','--keep-viewer-alive','0',
        '--device','auto']

def prepare():
    if RECORD.exists() or OUTPUT.exists():raise RuntimeError('v4 already prepared or started; inspect its record. Never overwrite.')
    cfg=json.loads((SOURCE/'config.json').read_text())
    assert cfg['num_iterations']==40000 and cfg['cap_max']==2500000
    assert cfg['sh_degree']==0 and cfg['auto_scale_poses'] is False
    assert cfg['depth_dir']=='depths-trusted-scale' and cfg['input_depth_is_ray_depth'] is True
    assert cfg['warp_to_pinhole'] is True and cfg['train_resolution_divisor']==1
    OUTPUT.mkdir(parents=True)
    hashes={}
    for name in FILES:
        src=SOURCE/name;dst=OUTPUT/name
        assert src.is_file()
        dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst)
        source_hash=sha(src);assert sha(dst)==source_hash
        hashes[name]={'sha256':source_hash,'bytes':src.stat().st_size,'copy_verified':True}
    record={'status':'prepared','prepared_unix':time.time(),'source_run':str(SOURCE),
        'new_run':str(OUTPUT),'source_files':hashes,'command':command(),
        'source_checkpoint_step':40000,'target_step':50000,'maximum_additional_iterations':10000,
        'changes':{'num_iterations':50000,'cap_max':3000000,'refine_stop_iter':48000,
            'refine_stop_num_iter':2000,'max_world_size':.12,'normal_reg_weight':.1,
            'normal_supervision_weight':.06,'depth_supervision_weight':.1},
        'unchanged':'SH0, trusted scale-only ray depth, original dataset/masks/poses, fisheye warp, resolution1, scene frame.',
        'scope':'One bounded combined geometry-prior/refinement and LR-schedule trial; no UV mesh extraction.',
        'lr_schedule_note':'max_steps remains null; num_iterations50k also changes LR progress from the prior40k schedule.',
        'checkpoint_policy':'Only latest checkpoint within new run; original v3 checkpoint and all source state preserved.',
        'gpu_start_gate':'Do not start until osmo_format explicitly reports dense photo bake and comparisons complete.'}
    save(record);print(json.dumps(record,indent=2),flush=True)

def run(ready_note):
    record=json.loads(RECORD.read_text())
    if record['status']!='prepared':raise RuntimeError('Only a prepared never-started v4 may run.')
    if not ready_note:raise RuntimeError('Explicit completion note from photo-bake agent required.')
    for name,details in record['source_files'].items():
        assert sha(SOURCE/name)==details['sha256']
        assert sha(OUTPUT/name)==details['sha256']
    assert command()==record['command']
    LOG.parent.mkdir(parents=True,exist_ok=True)
    if LOG.exists():raise RuntimeError('Training log already exists; no repeated trial.')
    env=os.environ.copy();env['OMP_NUM_THREADS']='16'
    record.update(status='starting',started_unix=time.time(),gpu_completion_note=ready_note,log=str(LOG))
    save(record)
    with LOG.open('xb',buffering=0) as log:
        process=subprocess.Popen(record['command'],env=env,cwd=RUN,stdout=log,stderr=subprocess.STDOUT)
        record.update(status='running',pid=process.pid);save(record)
        print(json.dumps({'status':'running','pid':process.pid,'log':str(LOG),'record':str(RECORD)},indent=2),flush=True)
        result=process.wait()
    unchanged={name:sha(SOURCE/name)==details['sha256'] for name,details in record['source_files'].items()}
    record.update(status='complete' if result==0 else 'failed',exit_code=result,
        elapsed_seconds=time.time()-record['started_unix'],original_source_files_unchanged=unchanged)
    save(record);print(json.dumps(record,indent=2),flush=True)
    print(LOG.read_text(errors='replace')[-3500:],flush=True)
    if not all(unchanged.values()):raise RuntimeError('Original source preservation check failed.')
    raise SystemExit(result)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--prepare',action='store_true');p.add_argument('--run',action='store_true');p.add_argument('--gpu-ready-note');a=p.parse_args()
    if a.prepare==a.run:p.error('Choose exactly one: --prepare or --run')
    if a.prepare:prepare()
    else:run(a.gpu_ready_note)
