from pathlib import Path
import json
from PIL import Image,ImageDraw,ImageFont
import numpy as np
W=Path(__file__).resolve().parent;A=W/'display-ablation';data=json.loads((A/'measurements.json').read_text());font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',23)
centers={'fridge':(430,455),'fan':(175,350),'dining':(250,350),'bathroom':(317,250)}
rows=[]
for label,(cx,cy) in centers.items():
    sheet=Image.new('RGB',(1800,660),'#18232f');draw=ImageDraw.Draw(sheet)
    base=None
    for column,name in enumerate(['baseline','all-source','combined']):
        row=next(r for r in data['results'] if r['name']==name);v=next(v for v in row['views'] if v['label']==label);im=Image.open(v['viewportFile']).convert('RGB')
        side=946;xc=(1920-side)/2+cx/600*side;yc=102+cy/600*side;left=max(0,min(1320,round(xc-300)));top=max(0,min(480,round(yc-300)))
        crop=im.crop((left,top,left+600,top+600));crop.save(A/f'{name}-{label}-crop600.png');sheet.paste(crop,(column*600,60));draw.text((column*600+12,12),name,font=font,fill='white')
        pixels=np.asarray(crop,dtype=float)
        if base is None:base=pixels
        delta=float(np.sqrt(np.mean((pixels-base)**2)));rows.append({'view':label,'variant':name,'cropBoxCSSPixels':[left,top,left+600,top+600],'RMSEversusBaseline255':delta,'notGroundTruthScore':True})
        native=Image.open(v['canvasFile']).convert('RGB');scale=native.width/1920;nx=int(xc*scale);ny=int((yc-102)*scale);native.crop((nx-300,ny-300,nx+300,ny+300)).save(A/f'{name}-{label}-crop600-native.png')
    sheet.save(A/f'comparison-{label}.png')
(A/'comparison-analysis.json').write_text(json.dumps({'rows':rows,'CSSCropMeaning':'600x600 unscaled crops of 1920x1080 browser screenshots. Separate crop600-native files retain 1:1 native drawing-buffer pixels.','performanceCaution':'Headless render loop reached its refresh cap; 240 Hz results are not mobile or real interaction benchmarks.','conclusion':'Viewer settings comparison saved. Visual inspection is required; RMSE against baseline only measures change, not improvement.'},indent=2))
print(json.dumps(rows,indent=2))
