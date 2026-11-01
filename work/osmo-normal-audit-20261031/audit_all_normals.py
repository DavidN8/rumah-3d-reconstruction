"""Read-only, CPU-only trusted-depth normal conditioning over accepted fits."""
from pathlib import Path
import importlib.util
import json
import time
import numpy as np
import cv2

ROOT=Path(r'C:\Users\bombe\OneDrive\Documents\ChatGPT\Ruang Kamare\roomscan-reconstruction\data\20261031_OSMO360\lite-v1')
DATA=ROOT/'dataset'
spec=importlib.util.spec_from_file_location('seed_fisheye',Path(__file__).parents[1]/'osmo-reconstruct-20261031/seed_fisheye.py')
s=importlib.util.module_from_spec(spec);spec.loader.exec_module(s)
cameras,images,_=s.read_model(DATA/'sparse/0');image_by_name={im['name']:im for im in images.values()}
fits=json.loads((ROOT/'analysis/seed-fisheye.json').read_text())['frames']
names=sorted(name for name,fit in fits.items() if fit.get('accepted_fit'))
ray_cache={};rows=[];started=time.monotonic()
out=Path(__file__).with_name('all-accepted-normal-alignment-audit.json')

def tangent(depth,rays,y,x,step=3):
    dx=depth[y,x+step,None]*rays[y,x+step]-depth[y,x-step,None]*rays[y,x-step]
    dy=depth[y+step,x,None]*rays[y+step,x]-depth[y-step,x,None]*rays[y-step,x]
    normal=np.cross(dx,dy);length=np.linalg.norm(normal,axis=1)
    normal/=np.maximum(length[:,None],1e-12)
    normal[np.sum(normal*rays[y,x],axis=1)>0]*=-1
    return normal,length

def angles(a,b,absolute=False):
    dot=np.clip(np.sum(a*b,axis=1),-1,1)
    if absolute:dot=np.abs(dot)
    return np.degrees(np.arccos(dot))

for number,name in enumerate(names,1):
    row={'name':name,'fitScale':fits[name]['scale'],'fitOffset':fits[name]['offset'],
         'fitOffsetFraction':abs(fits[name]['offset'])/fits[name]['sparse_range_median']}
    try:
        rel=Path(name).with_suffix('.png');paths=[DATA/leaf/rel for leaf in ['depths','depths-aligned','normals','masks']]
        before={str(p):[p.stat().st_size,p.stat().st_mtime_ns] for p in paths}
        depth,valid=s.load_depth(paths[0]);aligned,avalid=s.load_depth(paths[1]);h,w=depth.shape
        im=image_by_name[name];cam=cameras[im['camera_id']];key=(im['camera_id'],w,h)
        if key not in ray_cache:
            model=s.Fisheye(cam,w,h)
            yy,xx=np.meshgrid(np.arange(h)+.5,np.arange(w)+.5,indexing='ij')
            rays,rayvalid=model.unproject(np.stack([xx,yy],axis=-1))
            ray_cache[key]=(rays.astype(np.float32),rayvalid)
        rays,rayvalid=ray_cache[key]
        mask=cv2.imread(str(paths[3]),cv2.IMREAD_GRAYSCALE)
        if mask is None:raise ValueError('Missing person/border mask')
        if mask.shape!=(h,w):mask=cv2.resize(mask,(w,h),interpolation=cv2.INTER_NEAREST)
        valid&=avalid&(mask>127)&rayvalid
        valid=cv2.erode(valid.astype(np.uint8),np.ones((7,7),np.uint8))>0
        maxd=cv2.dilate(depth,np.ones((7,7),np.uint8));mind=cv2.erode(depth,np.ones((7,7),np.uint8))
        valid&=(maxd-mind)/np.maximum(depth,1e-12)<.05
        valid[:3]=False;valid[-3:]=False;valid[:,:3]=False;valid[:,-3:]=False
        grid=np.zeros_like(valid);grid[3:-3:6,3:-3:6]=True;yy,xx=np.nonzero(valid&grid)
        if len(yy)>5000:
            chosen=np.linspace(0,len(yy)-1,5000).astype(np.int64);yy=yy[chosen];xx=xx[chosen]
        png=cv2.imread(str(paths[2]),cv2.IMREAD_COLOR)
        if png is None:raise ValueError('Missing predicted normal map')
        if png.shape[:2]!=(h,w):png=cv2.resize(png,(w,h),interpolation=cv2.INTER_LINEAR)
        predicted=png[yy,xx,::-1].astype(np.float32)/127.5-1
        plen=np.linalg.norm(predicted,axis=1);predicted/=np.maximum(plen[:,None],1e-12)
        raw_normal,raw_length=tangent(depth,rays,yy,xx);aligned_normal,aligned_length=tangent(aligned,rays,yy,xx)
        keep=(plen>.75)&(plen<1.25)&(raw_length>1e-10)&(aligned_length>1e-10)
        predicted=predicted[keep];raw_normal=raw_normal[keep];aligned_normal=aligned_normal[keep]
        if len(predicted)<100:raise ValueError(f'Only {len(predicted)} smooth valid samples')
        changed=angles(raw_normal,aligned_normal);raw_predicted=angles(predicted,raw_normal,True);aligned_predicted=angles(predicted,aligned_normal,True)
        q=lambda a:np.percentile(a,[10,50,90,95]).tolist()
        med_change=float(np.median(changed));med_raw=float(np.median(raw_predicted));med_align=float(np.median(aligned_predicted))
        reasons=[]
        if med_change>10:reasons.append('median_raw_to_aligned_geometric_angle_over_10deg')
        if med_align>12:reasons.append('median_predicted_to_aligned_plane_angle_over_12deg')
        unchanged=all(before[str(p)]==[p.stat().st_size,p.stat().st_mtime_ns] for p in paths)
        row.update(samples=len(predicted),rawToAlignedMedianDegrees=med_change,predictedToRawMedianDegrees=med_raw,
                   predictedToAlignedMedianDegrees=med_align,rawToAlignedP10P50P90P95=q(changed),
                   predictedToRawP10P50P90P95=q(raw_predicted),predictedToAlignedP10P50P90P95=q(aligned_predicted),
                   rejectDepth=bool(reasons),rejectReasons=reasons,uncertainRawNormalBaseline=med_raw>12,
                   mapsUnchanged=unchanged,assessment='valid')
    except Exception as exc:
        row.update(assessment='uncertain',reason=str(exc),rejectDepth=False,uncertainRawNormalBaseline=True)
    rows.append(row)
    if number%25==0:print(json.dumps({'progress':number,'total':len(names),'rejected':sum(r.get('rejectDepth',False) for r in rows)}),flush=True)

rejects=[r['name'] for r in rows if r.get('rejectDepth')]
uncertain=[r['name'] for r in rows if r.get('uncertainRawNormalBaseline')]
valid=[r for r in rows if r.get('assessment')=='valid']
passed=[r['name'] for r in valid if not r.get('rejectDepth')]
trusted=[r['name'] for r in valid if not r.get('rejectDepth') and not r.get('uncertainRawNormalBaseline')]
report={'date':'2026-10-31','mode':'read-only CPU audit, no GPU, no input changes','gates':{'rawToAlignedMedianDegrees':10,'predictedToAlignedMedianDegrees':12,'uncertainRawBaselineMedianDegrees':12},
        'samplePolicy':'At most5000 samples on6px grid; +/-3px central tangents; raw7x7 depth span<5%;7x7 eroded valid/person/border mask; predicted normals RGB[-1,1]. Geometric normals face camera.',
        'acceptedFitFrames':len(names),'validlyAssessedFrames':len(valid),'rejectedDepthFrames':len(rejects),'uncertainBaselineFrames':len(uncertain),
        'gatePassFrames':len(passed),'conservativelyTrustedFrames':len(trusted),'rejectNames':rejects,'uncertainRawNormalBaselineNames':uncertain,
        'gatePassNames':passed,'trustedNamesConservative':trusted,'inputMapsUnchanged':all(r.get('mapsUnchanged',False) for r in valid),
        'elapsedSeconds':time.monotonic()-started,'frames':rows}
out.write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in report.items() if k not in ['frames','gatePassNames','trustedNamesConservative']},indent=2),flush=True)
