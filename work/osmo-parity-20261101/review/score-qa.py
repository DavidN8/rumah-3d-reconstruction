from pathlib import Path
import json,math
import numpy as np
from PIL import Image,ImageDraw,ImageFont
W=Path(__file__).resolve().parent;Q=W/'qa';font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',24)
boxes={'fridge':(950,480,1550,1080),'fan':(400,300,1000,900),'dining':(200,400,800,1000),'bathroom':(660,180,1260,780)}
rows=[]
models=list(json.loads((Q/'metadata.json').read_text())['models'])
for label,box in boxes.items():
    gt=np.array(Image.open(Q/(label+'-source.png')).convert('RGB'),dtype=float);mask=np.array(Image.open(Q/(label+'-keep.png')))>127;x0,y0,x1,y1=box
    for model in models:
        path=Q/f'{model}-{label}.png'
        if not path.exists():continue
        image=Image.open(path).convert('RGB');pr=np.array(image,dtype=float);error=gt-pr;mse=float(np.mean(error[mask]**2));cm=mask[y0:y1,x0:x1];ce=error[y0:y1,x0:x1];cropMse=float(np.mean(ce[cm]**2));
        row={'model':model,'view':label,'validFraction':float(mask.mean()),'psnrDb':10*math.log10(255**2/mse),'rmse255':math.sqrt(mse),'cropPSNR':10*math.log10(255**2/cropMse),'cropRMSE255':math.sqrt(cropMse),'cropBox':box,'GT':'Native photograph remapped by camera only; source keep-mask; no image registration or error-based masking'};rows.append(row)
        image.crop(box).save(Q/f'{model}-{label}-crop600.png')
    newest=sorted(k for k in models if k.startswith('new-full-'))
    groups=[('pilots',['source','pilot-base','pilot-sharp']),('delivery',['source','old-full','mesh-photo'])]
    if 'fusion-photo' in models:groups.append(('fusion',['source','old-full','fusion-photo']))
    if 'fusion-filled' in models:groups.append(('coherent',['source','old-full','fusion-filled']))
    if 'poisson-photo' in models:groups.append(('poisson',['source','old-full','poisson-photo']))
    if 'rgb-only-mip' in models:groups.append(('geometry-test',['source','pilot-sharp','rgb-only-mip']))
    if 'no-appearance-correction' in models:groups.append(('appearance-test',['source','rgb-only-3dgs','no-appearance-correction']))
    if 'sparse-rgb-only' in models:groups.append(('seed-test',['source','rgb-only-3dgs','sparse-rgb-only']))
    if newest:groups.append(('newest',['source','old-full',newest[-1]]))
    for group,which in groups:
        if group=='delivery' and not (Q/f'mesh-photo-{label}.png').exists():continue
        sheet=Image.new('RGB',(1800,650),'#172530');d=ImageDraw.Draw(sheet)
        for col,key in enumerate(which):
            path=Q/(label+'-source.png') if key=='source' else Q/f'{key}-{label}.png';im=Image.open(path).convert('RGB');sheet.paste(im.crop(box),(col*600,50));d.text((col*600+12,10),key,font=font,fill='white')
        sheet.save(Q/f'{group}-{label}.png')
report={'rows':rows,'scope':'Four fixed full-viewport 1920x1080 camera views, no per-image alignment. Three are source training timestamps and bathroom is appearance-held-out. Same-capture SfM is not independent geometry truth. Pilot steps and budgets match each other; original full uses a larger budget and more steps.','physicalPhoneTests':False}
(Q/'scores.json').write_text(json.dumps(report,indent=2));print(json.dumps([{k:v for k,v in r.items() if k in ['model','view','psnrDb','cropPSNR']} for r in rows],indent=2))
