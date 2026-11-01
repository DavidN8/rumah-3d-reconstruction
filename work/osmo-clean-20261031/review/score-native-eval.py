"""Score every native held-out render on its real binary keep-mask.

Match saved GT images to explicit pinhole JPEGs by measured RGB similarity,
requiring a unique bijection and a full-resolution RMSE below 2/255. Never
assume the trainer's eval index is chronological. No reconstruction is changed.
"""
import os
for key in ['OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS']:os.environ[key]='1'
from pathlib import Path
import hashlib,json,math
import numpy as np
from PIL import Image,ImageDraw
HERE=Path(__file__).resolve().parent
ROOT=Path('C:/Users/bombe/OneDrive/Documents/ChatGPT/Ruang Kamare/roomscan-reconstruction/data/20261031_OSMO360/clean-v3/explicit-full-v1')
DS=ROOT/'dataset';TRAIN=ROOT/'training/osmo-explicit-depth-v1'
audit=json.loads((DS/'explicit-pinhole-audit.json').read_text())
views=[v for v in audit['views'] if v['sourceSplit']=='eval']
gts=sorted(TRAIN.glob('eval-gt-*.png'))
assert len(views)==len(gts)==188
def rgb(p,size=None):
    im=Image.open(p).convert('RGB')
    if size:im=im.resize(size,Image.Resampling.BOX)
    return np.asarray(im)
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
original=np.stack([rgb(DS/'images'/v['name'],(64,64)).reshape(-1) for v in views]).astype(np.float64)
targets=np.stack([rgb(p,(64,64)).reshape(-1) for p in gts]).astype(np.float64)
dist=np.maximum(0,(targets*targets).sum(1)[:,None]+(original*original).sum(1)[None,:]-2*targets@original.T)/original.shape[1]
matches=dist.argmin(1)
assert len(set(matches.tolist()))==188,'GT/source matching is not a unique bijection'
rows=[];total_sse=0.;total_channels=0
for i,(gt_path,j) in enumerate(zip(gts,matches)):
    view=views[int(j)];source=DS/'images'/view['name'];mask_path=DS/'masks'/Path(view['name']).with_suffix('.png');render=gt_path.with_name(gt_path.name.replace('eval-gt-','eval-render-'))
    gt=rgb(gt_path);source_rgb=rgb(source);pred=rgb(render)
    assert gt.shape==source_rgb.shape==pred.shape==(1200,1200,3)
    exact_rmse=float(np.sqrt(np.mean((gt.astype(np.float64)-source_rgb)**2)))
    assert exact_rmse<2,(gt_path.name,view['name'],exact_rmse)
    valid=np.asarray(Image.open(mask_path))>127
    assert valid.shape==gt.shape[:2] and valid.sum()>0
    errors=(gt.astype(np.float64)-pred)[valid];sse=float((errors*errors).sum());mse=sse/errors.size
    total_sse+=sse;total_channels+=errors.size
    rows.append({'evalIndex':int(gt_path.stem.split('-')[-1]),**view,'gtSourceFullResolutionRmse255':exact_rmse,'validFraction':float(valid.mean()),'validPixels':int(valid.sum()),'rmse255':math.sqrt(mse),'psnrDb':10*math.log10(255**2/mse),'gt':str(gt_path),'render':str(render),'mask':str(mask_path),'sha256':{'gt':sha(gt_path),'render':sha(render),'mask':sha(mask_path)}})
    if (i+1)%40==0:print(f'Valid-pixel native evaluation {i+1}/188',flush=True)
ranked=sorted(rows,key=lambda r:r['psnrDb'])
sheet=Image.new('RGB',(1200,6*434),'#192028');draw=ImageDraw.Draw(sheet)
for row_index,row in enumerate(ranked[:6]):
    for col,(label,p) in enumerate([('GT photograph',row['gt']),('Native rendered prediction',row['render']),('White = scored / black = excluded',row['mask'])]):
        draw.text((col*400+8,row_index*434+8),f'{row["evalIndex"]}: {row["psnrDb"]:.2f}dB | {label}',fill='white')
        sheet.paste(Image.open(p).convert('RGB').resize((400,400),Image.Resampling.LANCZOS),(col*400,row_index*434+30))
sheet_path=HERE/'renders/full-eval-six-worst-valid.jpg';sheet.save(sheet_path,quality=95)
report={'status':'scored_pending_visual_review','scope':'All 188 appearance-held-out explicit pinhole views; same-capture SfM is not independent geometric ground truth. Scores use exact unchanged binary keep-masks, including exclusion of lens padding, operator and mirrors. No post-hoc pixel-error selection or image alignment.','matching':'Unique 188-to-188 RGB GT/source bijection, independently checked at 1200x1200','views':188,'meanPsnrDb':float(np.mean([r['psnrDb'] for r in rows])),'medianPsnrDb':float(np.median([r['psnrDb'] for r in rows])),'minimumPsnrDb':ranked[0]['psnrDb'],'weightedPsnrDb':10*math.log10(255**2/(total_sse/total_channels)),'weightedRmse255':math.sqrt(total_sse/total_channels),'maximumGtSourceRmse255':max(r['gtSourceFullResolutionRmse255'] for r in rows),'worstSixSheet':str(sheet_path),'rows':rows}
out=ROOT/'analysis/valid-native-evaluation.json';out.write_text(json.dumps(report,indent=2))
print(json.dumps({k:v for k,v in report.items() if k!='rows'},indent=2))
