from pathlib import Path
import subprocess,json,sys
b=Path(__file__).resolve().parent
approved=json.loads((b/'pinhole-repairs/approved-audit.json').read_text())['frames'];tail=json.loads((b/'tail-head-selection.json').read_text())['selected']
sets={cam:{r['source_frame'] for r in approved if r['camera']==cam and r['approved']} for cam in ['cam0','cam1']};sets['cam0'].update(r['source_frame'] for r in tail);sets['cam1'].update([1083,1704,1842])
(b/'final-changed-frames.json').write_text(json.dumps({c:sorted(ns) for c,ns in sets.items()},indent=2))
for cam,ns in sets.items():
 subprocess.run([sys.executable,str(b/'compose_reviewed.py'),'--cameras',cam,'--source-frames',*[str(n) for n in sorted(ns)]],check=True)
 subprocess.run([sys.executable,str(b/'build_masks.py'),'finalize','--candidate','--operator-layer','operator-reviewed','--cameras',cam,'--source-frames',*[str(n) for n in sorted(ns)]],check=True)
print('Changed masks recomposed and candidate-final refreshed',flush=True)
