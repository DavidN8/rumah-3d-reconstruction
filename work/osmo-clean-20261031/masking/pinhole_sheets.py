from pathlib import Path
from PIL import Image,ImageDraw
import math,json
b=Path(__file__).resolve().parent
fs=sorted((b/'pinhole-repairs').glob('cam*/*/selected-overlay.jpg'),key=lambda p:(p.parent.parent.name,int(p.parent.name)))
for start in range(0,len(fs),12):
 group=fs[start:start+12];out=Image.new('RGB',(1600,math.ceil(len(group)/4)*432),'#222');d=ImageDraw.Draw(out)
 for i,p in enumerate(group):
  x=i%4*400;y=i//4*432;out.paste(Image.open(p).resize((400,400)),(x,y+32));d.text((x+5,y+5),p.parent.parent.name+' '+p.parent.name,fill='white')
 out.save(b/'review'/f'pinhole-views-{start:03d}.jpg')
