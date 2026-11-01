from pathlib import Path
import json,os,subprocess,time
ROOT=Path(r'C:\Users\bombe\OneDrive\Documents\ChatGPT\Ruang Kamare\roomscan-reconstruction\data')
RUN=ROOT/'20261031_OSMO360/lite-v1';NAME='osmo-lite-trusted-v3'
report=json.loads((RUN/'analysis/trusted-depth-scale.json').read_text())
checkpoint=RUN/f'training/{NAME}/step-000020000.ckpt'
assert (checkpoint/'state.tar').is_file() and (checkpoint/'splat.ply').is_file()
assert (RUN/'dataset/depths-trusted-scale').is_dir()
record_path=RUN/'analysis/train-trusted-v3.json'
if record_path.exists():raise RuntimeError('Trusted resume already started; inspect its record.')
command=[str(ROOT/'20261019_095800/runtime/spirula/bin/spirula.exe'),'train','--resume',str(checkpoint),
    '--depth-dir','depths-trusted-scale','--apply-loss-for-mask','0','--num-iterations','40000',
    '--output-dir-prefix',str(RUN/'training'),'--output-dir-name',NAME,'--disable-viewer','1','--keep-viewer-alive','0','--device','auto']
record={'status':'running','started_unix':time.time(),'command':command,
        'source_checkpoint_step':20000,'pose_and_coordinate_frame_unchanged':True,
        'change':'Trusted scale-only ray depth; no affine radial offsets. RGB and raw normal views retained.'}
record_path.write_text(json.dumps(record,indent=2));env=os.environ.copy();env['OMP_NUM_THREADS']='16'
for k in ['CUDA_VISIBLE_DEVICES','GPU_DUTY_CYCLE','SS_GPU_DUTY_CYCLE']:env.pop(k,None)
print('Resuming trusted-depth refinement at step20000',flush=True)
with (RUN/'logs/train-trusted-v3.log').open('wb',buffering=0) as log:
    r=subprocess.run(command,env=env,cwd=RUN,stdout=log,stderr=subprocess.STDOUT)
record.update(status='complete' if r.returncode==0 else 'failed',exit_code=r.returncode,elapsed_seconds=time.time()-record['started_unix'])
record_path.write_text(json.dumps(record,indent=2));print(json.dumps(record),flush=True)
print((RUN/'logs/train-trusted-v3.log').read_text(errors='replace')[-1200:],flush=True)
raise SystemExit(r.returncode)
