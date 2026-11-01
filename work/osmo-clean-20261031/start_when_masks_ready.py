"""Queue camera alignment behind the explicit reviewed-mask release marker."""
from pathlib import Path
import hashlib, json, subprocess, sys, time
W=Path(__file__).resolve().parent
ready=W/'masking/masks-ready.json';audit=W/'masking/mask-audit.json'
print('Waiting for reviewed masks-ready.json; no SfM or training has started.',flush=True)
while not ready.is_file():time.sleep(5)
m=json.loads(ready.read_text())
if m.get('status')!='ready' or m.get('count')!=452:
    raise RuntimeError('Mask release marker is not complete')
if hashlib.sha256(audit.read_bytes()).hexdigest()!=m['mask_audit_sha256']:
    raise RuntimeError('Mask audit changed after review')
rows=json.loads(audit.read_text())['frames']
if len(rows)!=452:raise RuntimeError('Wrong mask audit count')
print('Reviewed mask release verified. Starting fresh SfM.',flush=True)
raise SystemExit(subprocess.call([sys.executable,str(W/'run_stage.py'),'sfm']))
