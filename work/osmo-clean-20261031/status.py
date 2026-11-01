from pathlib import Path
import json, re, time
W=Path(__file__).resolve().parent
R=Path(r'C:/Users/bombe/OneDrive/Documents/ChatGPT/Ruang Kamare/roomscan-reconstruction/data/20261031_OSMO360/clean-v3')
out={'native_images':sum(1 for _ in (R/'dataset/images').rglob('*.jpg')),
     'final_masks':sum(1 for _ in (R/'dataset/masks').rglob('*.png')),
     'stages':{}}
for stage in ['sfm','geometry','train']:
    path=R/f'analysis/{stage}.json'
    if not path.exists():continue
    s=json.loads(path.read_text());out['stages'][stage]={k:s[k] for k in ['status','exit_code','elapsed_seconds'] if k in s}
    out['stages'][stage]['elapsed_minutes']=round((time.time()-s['started_unix'])/60,1)
    log=R/f'logs/{stage}.log'
    if log.exists():
        with log.open('rb') as f:
            f.seek(max(0,log.stat().st_size-3500));tail=f.read().decode(errors='replace')
        clean=re.sub(r'\x1b\[[0-9;]*[A-Za-z]','',tail)
        lines=[line for line in clean.splitlines() if line.strip()]
        out['stages'][stage]['tail']='\n'.join(lines[-6:])[-1000:]
print(json.dumps(out,indent=2))
