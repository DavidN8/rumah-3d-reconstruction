"""Contact sheets from root-selected source thumbnails; no GPU or model writes."""
from pathlib import Path
from PIL import Image, ImageDraw
import argparse, json, math

p=argparse.ArgumentParser()
p.add_argument('--start',type=float,default=0)
p.add_argument('--end',type=float,default=66)
p.add_argument('--cam',choices=['cam0','cam1'],default='cam0')
p.add_argument('--tile',type=int,default=450)
p.add_argument('--count',type=int,default=12)
p.add_argument('--name',default='source')
a=p.parse_args()
base=Path(__file__).resolve().parent.parent
manifest=json.loads((base/'frame-selection.json').read_text())
records=[r for r in manifest['selected'] if a.start<=r['time_seconds']<=a.end]
out=base/'masking/review';out.mkdir(parents=True,exist_ok=True)
for start in range(0,len(records),a.count):
    chunk=records[start:start+a.count]
    canvas=Image.new('RGB',(3*a.tile,math.ceil(len(chunk)/3)*(a.tile+30)),'#24282e')
    d=ImageDraw.Draw(canvas)
    for j,r in enumerate(chunk):
        source=base/'thumbnails'/a.cam/f"sample_{r['source_frame']//3+1:06d}.jpg"
        im=Image.open(source).resize((a.tile,a.tile),Image.Resampling.LANCZOS)
        x,y=(j%3)*a.tile,(j//3)*(a.tile+30)
        canvas.paste(im,(x,y+30))
        d.text((x+5,y+5),f"{a.cam} n={r['source_frame']} t={r['time_seconds']:.2f}",fill='white')
    canvas.save(out/f'{a.name}-{a.cam}-{start:03d}.jpg',quality=92)
print(json.dumps([{'source_frame':r['source_frame'],'time_seconds':r['time_seconds']} for r in records]))
