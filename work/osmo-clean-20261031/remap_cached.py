"""Controlled SfM registration retry; preserve original evidence and reuse immutable matches."""
from pathlib import Path
import hashlib,json,os,shutil,subprocess,sys,time

W=Path(__file__).resolve().parent
R=Path(r'C:/Users/bombe/OneDrive/Documents/ChatGPT/Ruang Kamare/roomscan-reconstruction/data/20261031_OSMO360/clean-v3')
old=json.loads((R/'analysis/sfm.json').read_text())
if old['status']!='failed':raise RuntimeError('The original attempt must be stopped before retry')
archive=R/'analysis/sfm-first-attempt.json'
if archive.exists():raise RuntimeError('First attempt already archived; inspect instead of repeating')
archive.write_text(json.dumps(old,indent=2))
shutil.copy2(R/'logs/sfm.log',R/'logs/sfm-first-attempt.log')
matches=R/'sfm-native/matches.bin'
matches_sha=hashlib.sha256(matches.read_bytes()).hexdigest()
command=old['command']+['--reuse-features','keep','--reuse-matches','keep','--strong-pnp-inliers','200']
record={'stage':'sfm','attempt':2,'status':'running','started_unix':time.time(),'command':command,
        'registration_change':'Permit >=200 unique PnP inliers despite a diluted inlier fraction, retaining the rival-pose guard; max-error remains3 native pixels.',
        'source_matches_sha256':matches_sha,'preserved_first_attempt':str(archive),
        'lineage':'Same clean images, calibrated cameras, reviewed masks and verified correspondences. No scene seed, learned depth or trained checkpoint reused.'}
path=R/'analysis/sfm.json';path.write_text(json.dumps(record,indent=2))
env=os.environ.copy();env['OMP_NUM_THREADS']='12'
print('Starting cached registration retry; no feature/matcher rerun.',flush=True)
with (R/'logs/sfm.log').open('wb',buffering=0) as output:
    result=subprocess.run(command,stdout=output,stderr=subprocess.STDOUT,env=env,cwd=R)
record.update(status='finished' if result.returncode==0 else 'failed',exit_code=result.returncode,elapsed_seconds=time.time()-record['started_unix'],
              source_matches_unchanged=hashlib.sha256(matches.read_bytes()).hexdigest()==matches_sha)
path.write_text(json.dumps(record,indent=2))
print(json.dumps(record),flush=True)
print((R/'logs/sfm.log').read_text(errors='replace')[-2200:],flush=True)
sys.exit(result.returncode)
