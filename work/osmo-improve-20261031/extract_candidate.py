from pathlib import Path
import argparse, json, os, subprocess, time

ROOT=Path(r'C:\Users\bombe\OneDrive\Documents\ChatGPT\Ruang Kamare\roomscan-reconstruction\data')
OLD=ROOT/'20261031_OSMO360/lite-v1'
RUN=ROOT/'20261031_OSMO360/recovery-v2'
parser=argparse.ArgumentParser()
parser.add_argument('name',choices=['cull-off-probe','dense-cull-off','dense-cull-on','v4-probe','v4-texture'])
args=parser.parse_args()
for sub in ['analysis','logs','exports']:(RUN/sub).mkdir(parents=True,exist_ok=True)
record_path=RUN/'analysis'/f'{args.name}.json'
if record_path.exists():raise RuntimeError('Existing candidate record; inspect it instead of overwriting.')
probe=args.name in {'cull-off-probe','v4-probe'}
v4=args.name.startswith('v4-')
if v4:
    print('Waiting for the bounded v4 trial to finish',flush=True)
    deadline=time.monotonic()+900
    while True:
        training=json.loads((RUN/'analysis/train-surface-v4.json').read_text())
        if training['status']=='complete':break
        if training['status']=='failed' or time.monotonic()>deadline:raise RuntimeError('v4 training failed or wait expired.')
        time.sleep(2)
    assert training['exit_code']==0
    train=RUN/'training/osmo-surface-v4'
    assert (train/'step-000050000.ckpt').is_dir()
else:train=OLD/'training/osmo-lite-trusted-v3'
command=[str(ROOT/'20261019_095800/runtime/spirula/bin/spirula.exe'),'mesh',str(train),
         '--data',str(OLD/'dataset'),'--output',str(RUN/'exports'/args.name),
         '--format','glb' if probe else 'glb+jpeg94','--color','vertex' if probe else 'texture',
         '--texture-size','4096','--tex-gutter-px','4','--chart-angle-deg','60',
         '--max-grid-res','512','--merge-factor','1' if (probe or v4) else '0.8',
         '--merge-max-flip-deg','60','--bisection-iters','3','--carve-k','3',
         '--cull-unseen','1' if args.name in {'dense-cull-on','v4-probe'} else '0',
         '--fill-hole-ratio','0','--fill-hole-max-edges','12','--floater-min-faces','50',
         '--num-threads','16','--device','auto']
if not probe:command.extend(['--degenerate-angle-deg','2'])
record={'status':'running','started_unix':time.time(),'command':command,
        'reference':'Bounded v4 combined geometry-prior trial; original masks, poses and scene frame' if v4 else 'Unchanged final40000 checkpoint, masks, poses and scene frame from published v1',
        'purpose':'Test whether conservative self-occlusion cleanup removed actual captured surfaces' if probe else 'Retain more extracted detail with a4Kphoto atlas; no synthetic large-hole caps'}
record_path.write_text(json.dumps(record,indent=2))
env=os.environ.copy();env['OMP_NUM_THREADS']='16'
for key in ['CUDA_VISIBLE_DEVICES','GPU_DUTY_CYCLE','SS_GPU_DUTY_CYCLE']:env.pop(key,None)
print('Extracting '+args.name,flush=True)
with (RUN/'logs'/f'{args.name}.log').open('wb',buffering=0) as log:
    result=subprocess.run(command,env=env,cwd=RUN,stdout=log,stderr=subprocess.STDOUT)
record.update(status='complete' if result.returncode==0 else 'failed',exit_code=result.returncode,
              elapsed_seconds=time.time()-record['started_unix'])
record_path.write_text(json.dumps(record,indent=2))
print(json.dumps(record),flush=True)
print((RUN/'logs'/f'{args.name}.log').read_text(errors='replace')[-2000:],flush=True)
raise SystemExit(result.returncode)
