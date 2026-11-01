"""Compare real matched-camera screenshots and create an auditable contact sheet.

Run only after all seven original PLY and SOG PNGs have been captured by the
browser's Save render PNG control. No generated or repaired reference imagery.
"""
from pathlib import Path
import json,hashlib,math
import cv2
import numpy as np
from PIL import Image,ImageDraw
HERE=Path(__file__).resolve().parent;RENDERS=HERE/'renders'
metadata=json.loads((HERE/'clean-cameras.json').read_text());rows=[]
sheet=Image.new('RGB',(1200,7*434),'#192028');draw=ImageDraw.Draw(sheet)
def sha(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def similarity(a,b,valid):
    x=a.astype(np.float64);y=b.astype(np.float64);error=(x-y)[valid]
    mse=float(np.mean(error**2));rmse=math.sqrt(mse)
    c1=(.01*255)**2;c2=(.03*255)**2
    ux=cv2.GaussianBlur(x,(11,11),1.5);uy=cv2.GaussianBlur(y,(11,11),1.5)
    vx=cv2.GaussianBlur(x*x,(11,11),1.5)-ux*ux;vy=cv2.GaussianBlur(y*y,(11,11),1.5)-uy*uy
    cov=cv2.GaussianBlur(x*y,(11,11),1.5)-ux*uy
    ssim=((2*ux*uy+c1)*(2*cov+c2))/((ux*ux+uy*uy+c1)*(vx+vy+c2))
    interior=cv2.erode(valid.astype(np.uint8),np.ones((11,11),np.uint8))>0
    return {'rmse255':rmse,'psnrDb':float(10*math.log10(255**2/mse)) if mse else None,'ssim':float(ssim[interior].mean())}
for i,p in enumerate(metadata['presets'],1):
    source_path=Path(p['sourceFile']);mask_path=source_path.with_name(source_path.stem+'-valid.png')
    native_path=RENDERS/f'clean-fullNative-pose-{i}.png';sog_path=RENDERS/f'clean-fullSog-pose-{i}.png'
    native=Image.open(native_path).convert('RGB');packed=Image.open(sog_path).convert('RGB')
    if native.size!=(600,600) or packed.size!=native.size:raise ValueError('Expected matching 600-square actual renders')
    photo=Image.open(source_path).convert('RGB').resize(native.size,Image.Resampling.LANCZOS)
    valid=np.array(Image.open(mask_path).resize(native.size,Image.Resampling.NEAREST))>127
    a,b,c=map(np.asarray,[photo,native,packed])
    row={'pose':i,'name':p['name'],'timestampSeconds':p['sourceTimeSeconds'],'split':p['split'],'validFraction':float(valid.mean()),'nativeVsSource':similarity(a,b,valid),'packedVsSource':similarity(a,c,valid),'packingVsNative':similarity(b,c,np.ones(valid.shape,bool)),'sha256':{str(path.name):sha(path) for path in [source_path,mask_path,native_path,sog_path]}}
    rows.append(row)
    for col,(label,im) in enumerate([('Source photograph',photo),('Fresh original Gaussian',native),('Same Gaussian / SOG',packed)]):
        draw.text((col*400+8,(i-1)*434+8),f'{i}: {p["sourceTimeSeconds"]:.2f}s {p["split"]} | {label}',fill='white')
        sheet.paste(im.resize((400,400),Image.Resampling.LANCZOS),(col*400,(i-1)*434+30))
sheet.save(RENDERS/'clean-seven-source-native-sog.jpg',quality=95)
report={'purpose':__doc__,'scope':'Source timestamps held out from Gaussian training still participate in SfM pose estimation. Source comparisons are appearance diagnostics, not independent geometric ground truth. Packing comparison uses the same browser renderer, exact cameras, all source splats, SH2, and no LoD.','poses':rows,'packingMinimumPsnrDb':min(r['packingVsNative']['psnrDb'] for r in rows),'packingMeanRmse255':float(np.mean([r['packingVsNative']['rmse255'] for r in rows])),'evalMeanSourcePsnrDb':float(np.mean([r['nativeVsSource']['psnrDb'] for r in rows if r['split']=='eval'])),'contactSheet':'renders/clean-seven-source-native-sog.jpg'}
(HERE/'clean-matched-review.json').write_text(json.dumps(report,indent=2))
print(json.dumps({k:v for k,v in report.items() if k not in ['purpose','poses','scope']},indent=2))
