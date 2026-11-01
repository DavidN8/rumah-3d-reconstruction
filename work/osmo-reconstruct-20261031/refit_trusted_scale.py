"""Fresh scale-only ray-depth supervision; existing maps are never changed."""
from pathlib import Path
from argparse import Namespace
import json
import math
import time
import cv2
import numpy as np
import seed_fisheye as s

DATA=Path(r'C:\Users\bombe\OneDrive\Documents\ChatGPT\Ruang Kamare\roomscan-reconstruction\data\20261031_OSMO360\lite-v1\dataset')
OUT=DATA/'depths-trusted-scale';REPORT=DATA.parent/'analysis/trusted-depth-scale.json'
if OUT.exists() or REPORT.exists():raise FileExistsError('Trusted scale output/report already exists; inspect before rerunning')
ARGS=Namespace(depth_scale=.001,max_theta_degrees=105,allow_missing_masks=False,mask_erode=1,border=3)
started=time.monotonic();cameras,images,points=s.read_model(DATA/'sparse/0')
old=json.loads((DATA.parent/'analysis/seed-fisheye.json').read_text())['frames']
OUT.mkdir();rows=[];accepted=0
for number,(iid,image) in enumerate(sorted(images.items(),key=lambda item:item[1]['name']),1):
    name=image['name'];camera=cameras[image['camera_id']]
    row={'name':name,'accepted':False,'previousAffineAccepted':bool(old.get(name,{}).get('accepted_fit'))}
    if row['previousAffineAccepted']:row['previousAffineScale']=old[name]['scale'];row['previousAffineOffset']=old[name]['offset']
    try:
        frame=s.load_frame(DATA,image,camera,ARGS);h,w=frame['depth'].shape
        shape_scale=np.array([w/camera['width'],h/camera['height']]);xy=image['points2D_xy']*shape_scale
        valid=s.sample_map(frame['valid'].astype(np.uint8),xy,nearest=True)>0
        idx=np.array([j for j,pid in enumerate(image['point3D_ids']) if valid[j] and int(pid) in points and points[int(pid)]['track_len']>=3])
        if not len(idx):raise ValueError('No usable masked sparse observations')
        world=np.array([points[int(image['point3D_ids'][j])]['xyz'] for j in idx])
        xc=world@frame['R'].T+frame['t'];ranges=np.linalg.norm(xc,axis=1)
        projected,ok=frame['model'].project(xc);reprojection=np.linalg.norm((projected-xy[idx])/shape_scale,axis=1)
        rays,ray_ok=frame['model'].unproject(xy[idx]);angular=np.sum(rays*xc/np.maximum(ranges[:,None],1e-15),axis=1)
        raw=s.sample_map(frame['depth'],xy[idx])
        ok&=ray_ok&(reprojection<=4)&(angular>math.cos(math.radians(2)))&np.isfinite(raw)&(raw>0)&np.isfinite(ranges)&(ranges>0)
        raw=raw[ok];ranges=ranges[ok];reprojection=reprojection[ok]
        if len(raw)<30:raise ValueError(f'Only {len(raw)} usable observations')
        scale=float(np.median(ranges/raw));prediction=scale*raw
        error=np.abs(prediction-ranges)/ranges;inside=error<.10
        median=float(np.median(error));p90=float(np.percentile(error,90));fraction=float(inside.mean())
        sparse_iqr=float(np.subtract(*np.percentile(ranges,[75,25])));sparse_median=float(np.median(ranges))
        relative_span=sparse_iqr/sparse_median
        row.update(scale=scale,offset=0.,observations=len(raw),inliers=int(inside.sum()),inlierFraction=fraction,
                   medianRelativeResidual=median,p90RelativeResidual=p90,sparseRangeIQR=sparse_iqr,
                   sparseRangeMedian=sparse_median,sparseIQRRelative=relative_span,
                   medianReprojectionPixels=float(np.median(reprojection)),normalOrientationPreservedByUniformRayScale=True)
        reasons=[]
        if not np.isfinite(scale) or scale<=0:reasons.append('Scale must be finite and positive')
        if fraction<=.55:reasons.append('Inlier fraction must exceed .55 at 10% relative error')
        if median>=.10:reasons.append('Median relative residual must be below .10')
        if p90>=.25:reasons.append('p90 relative residual must be below .25')
        if relative_span<.08:reasons.append('Sparse range IQR / median must be at least .08')
        row['reasons']=reasons
        if not reasons:
            aligned=frame['depth']*scale;mm=np.rint(aligned*1000)
            valid=frame['valid']&np.isfinite(mm)&(mm>0)&(mm<65535)
            converted=np.where(valid,mm,0).astype(np.uint16)
            path=(OUT/Path(name)).with_suffix('.png');path.parent.mkdir(parents=True,exist_ok=True)
            if not cv2.imwrite(str(path),converted):raise RuntimeError(f'Failed writing {path}')
            row.update(accepted=True,output=str(path),validPixelFraction=float(valid.mean()),depthShape=[h,w])
            accepted+=1
    except Exception as exc:row['reason']=str(exc)
    rows.append(row)
    if number%40==0:print(f'Scale-only fits {number}/{len(images)}; trusted {accepted}',flush=True)
report={'method':'Per-frame positive scale only: median(observed sparse Euclidean range / raw metric MoGe ray range). No radial offset.',
        'depthUnits':'uint16 millimetres in unchanged normalized SfM world','inputDepthConvention':'Native MoGe ray distance',
        'normalOrientationPreserved':True,'sourceMapsUnchanged':True,'existingAlignedMapsUnchanged':True,
        'posesUnchanged':True,'rgbAndNormalsRetainedForRejectedDepthViews':True,
        'gates':{'minimumObservations':30,'maximumActualReprojectionPixels':4,'minimumInlierFractionExclusive':.55,
                 'inlierRelativeErrorThreshold':.10,'maximumMedianRelativeResidualExclusive':.10,
                 'maximumP90RelativeResidualExclusive':.25,'minimumSparseRangeIQRRelative':.08},
        'registeredViews':len(images),'previousAffineAccepted':sum(v.get('accepted_fit',False) for v in old.values()),
        'trustedScaleViews':accepted,'rgbNormalOnlyViews':len(images)-accepted,'newDepthDir':str(OUT),
        'elapsedSeconds':time.monotonic()-started,'frames':rows}
REPORT.write_text(json.dumps(report,indent=2,allow_nan=False),encoding='utf-8')
print(json.dumps({k:v for k,v in report.items() if k!='frames'},indent=2),flush=True)
print(json.dumps({'previousCollapsedFrames':[r for r in rows if r['name'] in ['cam0/frame_000052.jpg','cam0/frame_000053.jpg']]},indent=2),flush=True)
