from pathlib import Path
import json,os,sys
W=Path(__file__).resolve().parent;Q=W/'qa'
TRAIN=Path('C:/Users/bombe/OneDrive/Documents/ChatGPT/Ruang Kamare/roomscan-reconstruction/data/20261031_OSMO360/parity-20261101/explicit-1600/training/osmo-sharp-1600-full')
files=sorted(TRAIN.glob('step-*.ckpt/splat.ply'))
if not files:raise ValueError('No completed intermediate checkpoint')
file=files[-1];step=int(file.parent.name[5:14]);kind=f'new-full-{step:05d}';target=Q/(kind+'.ply')
with file.open('rb') as f:
    h=b''
    while not h.endswith(b'end_header\n'):h+=f.readline()
count=int(next(x.split()[-1] for x in h.decode().splitlines() if x.startswith('element vertex ')));properties=[x for x in h.decode().splitlines() if x.startswith('property ')]
if not all(x.split()[1]=='float' for x in properties) or file.stat().st_size!=len(h)+count*4*len(properties):raise ValueError('Checkpoint not completely written')
if not target.exists():os.link(file,target)
metadata=json.loads((Q/'metadata.json').read_text());metadata['models'][kind]={'url':'/review/qa/'+target.name,'format':'ply','bytes':target.stat().st_size};(Q/'metadata.json').write_text(json.dumps(metadata,indent=2));print(kind)
