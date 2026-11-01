"""Small CPU-only, read-only depth-fit probe; never writes dataset/seed.ply."""
from pathlib import Path
from argparse import Namespace
import json
import time
import cv2
import numpy as np
import seed_fisheye as s

DATA=Path(r'C:\Users\bombe\OneDrive\Documents\ChatGPT\Ruang Kamare\roomscan-reconstruction\data\20261031_OSMO360\lite-v1\dataset')
ARGS=Namespace(depth_scale=.001,max_theta_degrees=105,allow_missing_masks=False,mask_erode=1,border=3,
               min_track=3,max_sparse_error=4,min_fit_points=30,fit_threshold=.10,min_fit_fraction=.5)
t0=time.monotonic();cameras,images,points=s.read_model(DATA/'sparse/0')
selected=[]
for iid,image in sorted(images.items(),key=lambda item:item[1]['name']):
    if not image['name'].startswith('cam0/'):continue
    depth=DATA/'depths'/Path(image['name']).with_suffix('.png')
    if depth.is_file():selected.append((iid,image,depth))
    if len(selected)>=10:break
report={'date':'2026-10-31','probeOnly':True,'seedWritten':False,'registeredFrames':len(images),'sparsePoints':len(points),
        'depthInterpretation':'Native uint16 millimetre ray depth, then robust affine alignment to observed sparse Euclidean range',
        'sparseErrorSource':'Actual OPENCV_FISHEYE reprojection; stored point.error not trusted',
        'frames':[]}
for iid,image,depth_path in selected:
    before=depth_path.stat();camera=cameras[image['camera_id']]
    raw=cv2.imread(str(depth_path),cv2.IMREAD_UNCHANGED)
    row={'name':image['name'],'dtype':str(raw.dtype),'shape':list(raw.shape),'sourceCameraSize':[camera['width'],camera['height']],
         'sourceCameraParams':camera['params'].tolist(),'rawPositiveQuantiles':np.percentile(raw[raw>0],[0,5,50,95,100]).tolist()}
    frame=s.load_frame(DATA,image,camera,ARGS);row['maskedValidFraction']=float(frame['valid'].mean())
    try:row.update(accepted=True,fit=s.fit_frame(DATA,image,camera,points,ARGS))
    except Exception as exc:row.update(accepted=False,reason=str(exc))
    after=depth_path.stat();row['depthFileUnchanged']=[before.st_size,before.st_mtime_ns]==[after.st_size,after.st_mtime_ns]
    report['frames'].append(row)
    print(json.dumps({'name':row['name'],'accepted':row['accepted'],'fit':row.get('fit'),'reason':row.get('reason')}),flush=True)
report['testedFrames']=len(selected);report['acceptedFrames']=sum(row['accepted'] for row in report['frames'])
report['acceptedFraction']=report['acceptedFrames']/len(selected) if selected else 0
report['elapsedSeconds']=time.monotonic()-t0
out=DATA.parent/'analysis/seed-fit-probe.json';out.write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in report.items() if k!='frames'},indent=2),flush=True)
