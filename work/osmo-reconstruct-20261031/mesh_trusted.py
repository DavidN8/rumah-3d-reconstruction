from pathlib import Path
import json, os, subprocess, time

ROOT=Path(r'C:\Users\bombe\OneDrive\Documents\ChatGPT\Ruang Kamare\roomscan-reconstruction\data')
RUN=ROOT/'20261031_OSMO360/lite-v1'
TRAIN=RUN/'training/osmo-lite-trusted-v3'
OUTPUT=RUN/'exports/osmo-lite-trusted-source'
RECORD=RUN/'analysis/mesh-trusted-v3.json'
if RECORD.exists():
    raise RuntimeError('Mesh record already exists; inspect it before restarting.')
print('Waiting for the final trusted training checkpoint',flush=True)
deadline=time.monotonic()+900
while True:
    record=json.loads((RUN/'analysis/train-trusted-v3.json').read_text())
    if record['status']!='running':break
    if time.monotonic()>deadline:raise RuntimeError('Training wait exceeded 15 minutes; inspect the training job.')
    time.sleep(2)
assert record['status']=='complete' and record['exit_code']==0, 'Training must finish successfully first.'
assert (TRAIN/'step-000040000.ckpt').is_dir(), 'Final checkpoint required.'
command=[str(ROOT/'20261019_095800/runtime/spirula/bin/spirula.exe'),'mesh',str(TRAIN),
         '--data',str(RUN/'dataset'),'--output',str(OUTPUT),'--format','glb+jpeg90','--color','texture',
         '--texture-size','2048','--tex-gutter-px','4','--chart-angle-deg','60',
         '--max-grid-res','512','--merge-factor','1','--merge-max-flip-deg','60','--bisection-iters','3',
         '--carve-k','3','--fill-hole-ratio','0','--fill-hole-max-edges','12','--floater-min-faces','50',
         '--num-threads','16','--device','auto']
env=os.environ.copy();env['OMP_NUM_THREADS']='16'
for key in ['CUDA_VISIBLE_DEVICES','GPU_DUTY_CYCLE','SS_GPU_DUTY_CYCLE']:env.pop(key,None)
record={'status':'running','started_unix':time.time(),'command':command,
        'note':'Full height retained. Native topology-guarded merge1, conservative small hole fill12, 2048 photo atlas.'}
RECORD.write_text(json.dumps(record,indent=2))
print('Extracting final trusted Osmo mesh',flush=True)
with (RUN/'logs/mesh-trusted-v3.log').open('wb',buffering=0) as log:
    result=subprocess.run(command,env=env,cwd=RUN,stdout=log,stderr=subprocess.STDOUT)
record.update(status='complete' if result.returncode==0 else 'failed',exit_code=result.returncode,
              elapsed_seconds=time.time()-record['started_unix'])
RECORD.write_text(json.dumps(record,indent=2))
print(json.dumps(record),flush=True)
print((RUN/'logs/mesh-trusted-v3.log').read_text(errors='replace')[-2200:],flush=True)
raise SystemExit(result.returncode)
