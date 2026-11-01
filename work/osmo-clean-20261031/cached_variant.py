"""Test mapping settings using the same immutable calibrated images/features/matches."""
from pathlib import Path
import argparse,hashlib,json,os,shutil,subprocess,sys,time

W=Path(__file__).resolve().parent
R=Path(r'C:/Users/bombe/OneDrive/Documents/ChatGPT/Ruang Kamare/roomscan-reconstruction/data/20261031_OSMO360/clean-v3')
p=argparse.ArgumentParser();p.add_argument('label');p.add_argument('--max-error',type=float,default=3)
p.add_argument('--mapper',choices=['flat','bottom-up'],default='flat')
a=p.parse_args()
if not a.label.replace('-','').isalnum():raise ValueError('Use a plain label')
base=R/'sfm-native';output=R/('sfm-'+a.label)
if output.exists():raise FileExistsError(output)
current=json.loads((R/'analysis/sfm.json').read_text())
if current['status']=='running':raise RuntimeError('Another SfM attempt is still running')
archive=R/('analysis/sfm-before-'+a.label+'.json')
archive.write_text(json.dumps(current,indent=2))
shutil.copy2(R/'logs/sfm.log',R/('logs/sfm-before-'+a.label+'.log'))
output.mkdir()
for directory in ['features','.resume']:
    source=(base/directory).resolve()
    for item in source.rglob('*'):
        if not item.is_file():continue
        if not item.resolve().is_relative_to(source):raise ValueError('Cache escaped source workspace')
        destination=output/directory/item.relative_to(source)
        destination.parent.mkdir(parents=True,exist_ok=True);os.link(item,destination)
# Keep this small cache as an independent copy: an unexpected writer cannot alter
# the original verification evidence through a hardlink.
shutil.copy2(base/'matches.bin',output/'matches.bin')
matches_sha=hashlib.sha256((base/'matches.bin').read_bytes()).hexdigest()
first=json.loads((R/'analysis/sfm-first-attempt.json').read_text())
command=list(first['command']);command[command.index('-o')+1]=str(output)
command+=['--reuse-features','keep','--reuse-matches','keep','--strong-pnp-inliers','200',
          '--max-error',str(a.max_error),'--mapper',a.mapper]
record={'stage':'sfm','variant':a.label,'sfm_root':str(output),'status':'running','started_unix':time.time(),
        'command':command,'source_matches_sha256':matches_sha,
        'lineage':'Same clean images, masks, native calibration, feature rows and stricter3px verified correspondences. Mapping-only trial, no old scene/training/depth reuse.',
        'resolution_tolerance_note':'Old frontend1600px max-error3 was carried into native3840px extraction. A6px native mapping tolerance is still below its7.2px angular equivalent. Final measuredp95<=5px gate remains.'}
record_path=R/'analysis/sfm.json';record_path.write_text(json.dumps(record,indent=2))
print('Starting cached mapping variant '+a.label,flush=True)
env=os.environ.copy();env['OMP_NUM_THREADS']='12'
with (R/'logs/sfm.log').open('wb',buffering=0) as log:
    result=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,cwd=R,env=env)
record.update(status='finished' if result.returncode==0 else 'failed',exit_code=result.returncode,
              elapsed_seconds=time.time()-record['started_unix'],
              source_matches_unchanged=hashlib.sha256((output/'matches.bin').read_bytes()).hexdigest()==matches_sha)
record_path.write_text(json.dumps(record,indent=2))
print(json.dumps(record),flush=True)
print((R/'logs/sfm.log').read_text(errors='replace')[-1800:],flush=True)
sys.exit(result.returncode)
