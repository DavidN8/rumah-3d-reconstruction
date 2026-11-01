"""Isolated clean rebuild. Every invocation records exact commands and refuses stale outputs."""
from pathlib import Path
import hashlib, json, os, subprocess, sys, time

WORK=Path(__file__).resolve().parent
CAP=Path(r'C:/Users/bombe/OneDrive/Documents/ChatGPT/Ruang Kamare/roomscan-reconstruction/data/20261031_OSMO360')
RUN=CAP/'clean-v3';DS=RUN/'dataset'
CLI=WORK/'runtime/spirula-2026.10.30/spirula.exe'
MODELS=CAP.parent/'20261019_095800/runtime/spirula/models'
for folder in ['analysis','logs','training','exports']:(RUN/folder).mkdir(parents=True,exist_ok=True)
stage=sys.argv[1]
provenance={}
if stage=='sfm':
    m=json.loads((WORK/'frame-selection.json').read_text())
    for r in m['selected']:
        for lens in range(2):
            mask=DS/f'masks/cam{lens}'/(Path(r['filename']).stem+'.png')
            if not mask.is_file():raise RuntimeError(f'Missing mask {mask}')
    destination=RUN/'sfm-native'
    if destination.exists():raise RuntimeError('Fresh SfM output already exists; inspect rather than reuse silently.')
    command=[str(CLI),'sfm','auto',str(DS/'images'),'-o',str(destination),
        '--manifest',str(WORK/'geometry/sfm-manifest-native3840.json'),'--masks',str(DS/'masks'),
        '--camera-model','opencv-fisheye','--data-type','video','--quality','high',
        '--features','aliked-n16rot','--matcher','lightglue','--aliked-max-features','8192',
        '--max-image-size','3840','--pairs','prefilter','--sequence','cam0,cam1',
        '--prefilter-sequential','--overlap','20','--prefilter-neighbors','32',
        '--focal-trials','0','--no-refine-extra-params','--no-final-extra-params',
        '--audit','--threads','12','--device','auto']
elif stage=='geometry':
    command=[str(CLI),'geometry',str(DS),'--model',str(MODELS/'moge2-vitl-normal.onnx'),
        '--split','auto','--max-size','1064','--face-res','source',
        '--num-tokens','3600','--normal-format','png','--device','auto']
elif stage=='train':
    name='osmo-clean-normals-v1'
    if (RUN/'training'/name).exists():raise RuntimeError('Fresh training output already exists; refusing warm start.')
    audit_path=WORK/'geometry/fresh-sfm-preparation-audit.json'
    audit=json.loads(audit_path.read_text())
    review_path=RUN/'analysis/scene-review.json';review=json.loads(review_path.read_text())
    audit_sha=hashlib.sha256(audit_path.read_bytes()).hexdigest()
    if not audit.get('applied') or review.get('status')!='pass' or review.get('normalization_audit_sha256')!=audit_sha:
        raise RuntimeError('The current fresh scene has not passed its recorded review')
    for filename,expected in audit['written_files_sha256'].items():
        candidate=Path(filename)
        if not candidate.resolve().is_relative_to(DS.resolve()):raise RuntimeError('Prepared geometry escaped this dataset')
        if hashlib.sha256(candidate.read_bytes()).hexdigest()!=expected:raise RuntimeError(f'Prepared input changed: {candidate}')
    for item in audit['reprojection']['per_image']:
        normal=DS/'normals'/Path(item['name']).with_suffix('.png')
        if not normal.is_file() or normal.stat().st_size==0:raise RuntimeError(f'Missing normal guidance: {normal}')
    provenance={'normalization_audit_sha256':audit_sha,'scene_review_sha256':hashlib.sha256(review_path.read_bytes()).hexdigest(),
                'fresh_seed_sha256':hashlib.sha256((DS/'seed-train-sparse.ply').read_bytes()).hexdigest(),
                'registered_source_images':len(audit['reprojection']['per_image']),
                'learned_depth_supervision':False,'old_checkpoint_or_init_ply_used':False}
    command=[str(CLI),'train','360-camera','--data',str(DS),'--output-dir-prefix',str(RUN/'training'),
        '--output-dir-name',name,'--num-iterations','50000','--refine-stop-iter','35000',
        '--quality','high','--cap-max','3000000','--seed-pointcloud',str(DS/'seed-train-sparse.ply'),
        '--warp-to-pinhole','1','--train-resolution-divisor','1','--progressive-resolution','1',
        '--progressive-resolution-start','4','--progressive-resolution-full-at','0.3','--cache-images','disk',
        '--load-masks','1','--apply-loss-for-mask','0',
        '--load-depths','0','--depth-supervision-weight','0',
        '--load-normals','1','--normal-supervision-weight','0.01',
        '--distraction-robustness','mild','--floater-suppression','mild','--primitive','mip','--sh-degree','2',
        '--scene-center','none','--train-frame','points','--orientation-method','none',
        '--center-method','none','--auto-scale-poses','0','--eval-mode','filename','--validation-fraction','0',
        '--save-eval-images','1','--steps-per-save','5000',
        '--save-only-latest-checkpoint','1','--save-full-checkpoint','1',
        '--disable-viewer','1','--keep-viewer-alive','0','--device','auto']
else:raise ValueError(stage)
env=os.environ.copy();env['OMP_NUM_THREADS']='12'
for key in ['CUDA_VISIBLE_DEVICES','GPU_DUTY_CYCLE','SS_GPU_DUTY_CYCLE']:env.pop(key,None)
record={'stage':stage,'status':'running','started_unix':time.time(),'command':command,
    'lineage':'clean-v3 only; original source; no prior scene seed, depth alignment, or checkpoint',
    'runtime':'2026.10.30 (6ad73ef), isolated, verified release SHA256'}
record.update(provenance)
record_path=RUN/f'analysis/{stage}.json';record_path.write_text(json.dumps(record,indent=2))
print('Starting '+stage,flush=True)
with (RUN/f'logs/{stage}.log').open('wb',buffering=0) as output:
    result=subprocess.run(command,stdout=output,stderr=subprocess.STDOUT,env=env,cwd=RUN)
record.update(status='finished' if result.returncode==0 else 'failed',exit_code=result.returncode,elapsed_seconds=time.time()-record['started_unix'])
record_path.write_text(json.dumps(record,indent=2))
print(json.dumps(record),flush=True)
print((RUN/f'logs/{stage}.log').read_text(errors='replace')[-3500:],flush=True)
sys.exit(result.returncode)
