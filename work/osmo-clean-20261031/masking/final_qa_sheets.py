from pathlib import Path
from PIL import Image,ImageDraw
import json,numpy as np,math
b=Path('work/osmo-clean-20261031/masking');changes=json.loads((b/'final-changed-frames.json').read_text());rs={r['source_frame']:r for r in json.loads((b.parent/'frame-selection.json').read_text())['selected']}
for cam,ns in changes.items():
 for start in range(0,len(ns),12):
  group=ns[start:start+12];out=Image.new('RGB',(1600,math.ceil(len(group)/4)*432),'#222');d=ImageDraw.Draw(out)
  for i,n in enumerate(group):
   r=rs[n];im=Image.open(b.parent/'thumbnails'/cam/f'sample_{n//3+1:06d}.jpg').resize((400,400));a=np.asarray(im).copy();m=np.asarray(Image.open(b/'candidate-final'/cam/Path(r['filename']).with_suffix('.png')).resize((400,400)))<128;a[m]=a[m]*.55+np.array([255,15,50])*.45;x=i%4*400;y=i//4*432;out.paste(Image.fromarray(a),(x,y+32));d.text((x+5,y+5),str(n),fill='white')
  out.save(b/'review'/f'final-changed-{cam}-{start:03d}.jpg')
