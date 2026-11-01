from pathlib import Path
import json,hashlib,shutil,os
W=Path(__file__).resolve().parent;ROOT=W.parent
OLD=ROOT/'osmo-clean-20261031';P=W/'review/production';P.mkdir(parents=True,exist_ok=True)
records=[]
for file in (OLD/'review/production').iterdir():
    if file.is_file() and file.suffix in {'.js','.mjs','.html','.json','.ps1','.sh','.py'}:
        target=P/file.name
        if not target.exists():shutil.copy2(file,target)
        records.append({'path':str(file),'sha256':hashlib.sha256(file.read_bytes()).hexdigest(),'bytes':file.stat().st_size})
for name in ['frame-selection.json','build_explicit_pinhole.py','fit_explicit_depth.py','validate_explicit_depth.py','continue_explicit_full.py','run_logged_job.py']:
    if not (W/name).exists():shutil.copy2(OLD/name,W/name)
V=W/'review/vendor/spark/dist';V.mkdir(parents=True,exist_ok=True)
for file in (OLD/'review/vendor/spark/dist').iterdir():
    if file.is_file() and not (V/file.name).exists():os.link(file,V/file.name)
candidate=json.loads((P/'candidate.json').read_text())
candidate.update(file=str(OLD/'review/clean-final.sog'),cameras=str(W/'review/occupied-cameras.json'),releaseId='20261101-osmo-parity-v1')
(P/'candidate.json').write_text(json.dumps(candidate,indent=2))
(W/'baseline-preservation.json').write_text(json.dumps({'liveRelease':'20261031-osmo-clean-v1','sourceFiles':records,'iphoneHashes':{'fast':'2b811d124120e70dcecc25d06e5dc397e2a28f310403a21fdfa1e290c41c9d2b','full':'16f8963b043a766317497ee4281f4cf39c6b2190fafaaed51334734723c8b207'},'oldFilesModified':False},indent=2))
print('Isolated staging prepared:',P)
