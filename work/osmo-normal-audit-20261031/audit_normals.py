"""Read-only CPU comparison of raw/aligned ray-depth and MoGe normals."""
from pathlib import Path
import importlib.util
import itertools
import json
import numpy as np
import cv2

ROOT=Path(r'C:\Users\bombe\OneDrive\Documents\ChatGPT\Ruang Kamare\roomscan-reconstruction\data\20261031_OSMO360\lite-v1')
DATA=ROOT/'dataset'
spec=importlib.util.spec_from_file_location('seed_fisheye',Path(__file__).parents[1]/'osmo-reconstruct-20261031/seed_fisheye.py')
s=importlib.util.module_from_spec(spec);spec.loader.exec_module(s)
cameras,images,points=s.read_model(DATA/'sparse/0');image_by_name={im['name']:im for im in images.values()}
fits=json.loads((ROOT/'analysis/seed-fisheye.json').read_text())['frames']
names=['cam0/frame_000001.jpg','cam0/frame_000010.jpg','cam0/frame_000030.jpg','cam0/frame_000043.jpg',
       'cam0/frame_000052.jpg','cam0/frame_000053.jpg','cam1/frame_000001.jpg','cam1/frame_000093.jpg',
       'cam1/frame_000119.jpg','cam1/frame_000120.jpg']
if not fits.get(names[6],{}).get('accepted_fit'):
    names[6]=next(name for name,v in fits.items() if name.startswith('cam1/') and v.get('accepted_fit'))

def normals_for(depth,rays,step=3):
    p=depth[:,:,None]*rays
    dx=p[step:-step,2*step:]-p[step:-step,:-2*step]
    dy=p[2*step:,step:-step]-p[:-2*step,step:-step]
    cross=np.cross(dx,dy);length=np.linalg.norm(cross,axis=2)
    normal=cross/np.maximum(length[:,:,None],1e-12)
    center_rays=rays[step:-step,step:-step]
    normal[np.sum(normal*center_rays,axis=2)>0]*=-1
    return normal,length

def angle(a,b,absolute=False):
    dot=np.clip(np.sum(a*b,axis=1),-1,1)
    if absolute:dot=np.abs(dot)
    return np.degrees(np.arccos(dot))

report={'mode':'read-only CPU audit','mapMutation':False,'frameCount':0,'rows':[],
        'samplePolicy':'Central differences over +/-3px; 7x7 eroded valid mask; raw relative depth span below5% over7px; sampled on4px grid; predicted normals RGB decoded to[-1,1]. Geometric normals face camera.',
        'warning':'Absolute-dot angles compare tangent planes independently of global sign; best per-axis flip is a convention diagnostic, not a proposed map edit.'}
for name in names:
    fit=fits.get(name,{})
    if not fit.get('accepted_fit'):continue
    rel=Path(name).with_suffix('.png');dp=DATA/'depths'/rel;ap=DATA/'depths-aligned'/rel;npth=DATA/'normals'/rel;mp=DATA/'masks'/rel
    before={str(p):[p.stat().st_size,p.stat().st_mtime_ns] for p in [dp,ap,npth,mp]}
    depth,valid=s.load_depth(dp);aligned,avalid=s.load_depth(ap);h,w=depth.shape
    im=image_by_name[name];cam=cameras[im['camera_id']];model=s.Fisheye(cam,w,h)
    yy,xx=np.meshgrid(np.arange(h)+.5,np.arange(w)+.5,indexing='ij');rays,rayvalid=model.unproject(np.stack([xx,yy],axis=-1))
    mask=cv2.resize(cv2.imread(str(mp),cv2.IMREAD_GRAYSCALE),(w,h),interpolation=cv2.INTER_NEAREST)>127
    pred=cv2.cvtColor(cv2.resize(cv2.imread(str(npth),cv2.IMREAD_COLOR),(w,h),interpolation=cv2.INTER_LINEAR),cv2.COLOR_BGR2RGB).astype(float)/127.5-1
    plen=np.linalg.norm(pred,axis=2);pred/=np.maximum(plen[:,:,None],1e-12)
    valid&=avalid&mask&rayvalid&(plen>.75)&(plen<1.25)
    valid=cv2.erode(valid.astype(np.uint8),np.ones((7,7),np.uint8))>0
    maxd=cv2.dilate(depth,np.ones((7,7),np.uint8));mind=cv2.erode(depth,np.ones((7,7),np.uint8))
    valid&=(maxd-mind)/np.maximum(depth,1e-12)<.05
    nr,nrl=normals_for(depth,rays);na,nal=normals_for(aligned,rays)
    keep=valid[3:-3,3:-3]&(nrl>1e-10)&(nal>1e-10)
    grid=np.zeros_like(keep);grid[::4,::4]=True;keep&=grid
    nr=nr[keep];na=na[keep];pn=pred[3:-3,3:-3][keep];rr=rays[3:-3,3:-3][keep]
    flips=[]
    for signs in itertools.product([-1,1],repeat=3):
        flip=np.array(signs);scores=angle(nr,pn*flip,absolute=True)
        flips.append({'signs':list(signs),'medianPlaneAngle':float(np.median(scores))})
    flips.sort(key=lambda v:v['medianPlaneAngle'])
    q=lambda a:np.percentile(a,[10,50,90,95]).tolist()
    row={'name':name,'samples':len(nr),'scale':fit['scale'],'offset':fit['offset'],'offsetFraction':abs(fit['offset'])/fit['sparse_range_median'],
         'rawToAlignedGeometricAngleP10P50P90P95':q(angle(nr,na)),
         'predToRawPlaneAngleP10P50P90P95':q(angle(pn,nr,True)),
         'predToAlignedPlaneAngleP10P50P90P95':q(angle(pn,na,True)),
         'predToRawSignedAngleP10P50P90P95':q(angle(pn,nr)),
         'predPointsTowardCameraFraction':float(np.mean(np.sum(pn*rr,axis=1)<0)),
         'conventionFlipsBest':flips[:3],
         'geometricNormalChangeOver10DegFraction':float(np.mean(angle(nr,na)>10)),
         'mapsUnchanged':all(before[str(p)]==[p.stat().st_size,p.stat().st_mtime_ns] for p in [dp,ap,npth,mp])}
    report['rows'].append(row)
    print(json.dumps(row),flush=True)
report['frameCount']=len(report['rows'])
Path(__file__).with_name('normal-alignment-audit.json').write_text(json.dumps(report,indent=2))
