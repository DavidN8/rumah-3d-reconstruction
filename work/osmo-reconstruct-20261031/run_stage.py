from pathlib import Path
import json, os, subprocess, sys, time
ROOT=Path(r'C:\Users\bombe\OneDrive\Documents\ChatGPT\Ruang Kamare\roomscan-reconstruction\data')
RUN=ROOT/'20261031_OSMO360/lite-v1'
DS=RUN/'dataset'
RT=ROOT/'20261019_095800/runtime/spirula'
CLI=RT/'bin/spirula.exe'
for sub in ['analysis','logs','training','exports']:(RUN/sub).mkdir(parents=True,exist_ok=True)
stage=sys.argv[1]
NAME='osmo-lite-rectified-v2'
if stage=='sfm':
    manifest=json.loads(Path('work/osmo-format-20261031/sfm-manifest.json').read_text())
    manifest['image_dir']=(DS/'images').as_posix();manifest['mask_dir']=(DS/'masks').as_posix()
    path=RUN/'analysis/sfm-manifest.json';path.write_text(json.dumps(manifest,indent=2))
    command=[str(CLI),'sfm','auto',str(DS/'images'),'-o',str(RUN/'sfm-calibrated-v2'), '--manifest',str(path),
             '--masks',str(DS/'masks'),'--camera-model','opencv-fisheye',
             '--data-type','video','--quality','high','--features','aliked-n16rot','--matcher','lightglue',
             '--aliked-max-features','4096','--max-image-size','1600','--pairs','prefilter','--sequence','cam0,cam1',
             '--prefilter-sequential','--overlap','12','--prefilter-neighbors','20',
             '--focal-trials','0','--no-refine-extra-params','--no-final-extra-params','--audit','--threads','16','--device','auto']
elif stage=='geometry':
    command=[str(CLI),'geometry',str(DS),'--model',str(RT/'models/moge2-vitl-normal.onnx'),
             '--depth','--depth-units','mm','--ray-depth','yes','--split','auto','--max-size','768',
             '--num-tokens','1800','--normal-format','png','--device','auto']
elif stage=='train':
    if (RUN/'training'/NAME).exists():raise RuntimeError('Training directory exists; do not overwrite.')
    command=[str(CLI),'train','meshing','--data',str(DS),'--output-dir-prefix',str(RUN/'training'),
             '--output-dir-name',NAME,'--num-iterations','40000','--refine-stop-iter','30000',
             '--quality','high','--cap-max','2500000','--seed-pointcloud',str(DS/'seed.ply'),
             '--warp-to-pinhole','1','--train-resolution-divisor','1','--progressive-resolution','1','--progressive-resolution-full-at','0.25',
             '--load-depths','1','--depth-dir','depths-aligned','--input-depth-is-ray-depth','1',
             '--depth-unit-scale-factor','0.001','--depth-supervision-weight','0.05',
             '--load-normals','1','--normal-supervision-weight','0.02',
             '--distraction-robustness','mild','--floater-suppression','mild','--sh-degree','0',
             '--scene-center','none','--train-frame','points','--orientation-method','none','--center-method','none','--auto-scale-poses','0',
             '--eval-mode','all','--save-eval-images','0','--steps-per-save','5000','--save-only-latest-checkpoint','1',
             '--save-full-checkpoint','1','--disable-viewer','1','--keep-viewer-alive','0','--device','auto']
elif stage=='mesh':
    command=[str(CLI),'mesh',str(RUN/'training'/NAME),'--data',str(DS),
             '--output',str(RUN/'exports/osmo-lite-rectified-source'),'--format','glb+jpeg90','--color','texture',
             '--texture-size','4096','--tex-gutter-px','4','--chart-angle-deg','75',
             '--max-grid-res','512','--merge-factor','0.5','--bisection-iters','4',
             '--carve-k','3','--fill-hole-ratio','0','--fill-hole-max-edges','32','--floater-min-faces','50',
             '--num-threads','16','--device','auto']
else:raise ValueError(stage)
env=os.environ.copy();env['OMP_NUM_THREADS']='16'
for key in ['CUDA_VISIBLE_DEVICES','GPU_DUTY_CYCLE','SS_GPU_DUTY_CYCLE']:env.pop(key,None)
record={'stage':stage,'status':'running','started_unix':time.time(),'command':command}
record_path=RUN/f'analysis/{stage}.json';record_path.write_text(json.dumps(record,indent=2))
print('Starting '+stage,flush=True)
with (RUN/f'logs/{stage}.log').open('wb',buffering=0) as output:
    result=subprocess.run(command,stdout=output,stderr=subprocess.STDOUT,env=env,cwd=RUN)
record.update(status='finished' if result.returncode==0 else 'failed',exit_code=result.returncode,elapsed_seconds=time.time()-record['started_unix'])
record_path.write_text(json.dumps(record,indent=2));print(json.dumps(record),flush=True)
print((RUN/f'logs/{stage}.log').read_text(errors='replace')[-2500:],flush=True)
sys.exit(result.returncode)
