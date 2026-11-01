from pathlib import Path
import json,hashlib
import numpy as np
from PIL import Image,ImageDraw
W=Path(__file__).resolve().parent;OLD=W.parent/'osmo-clean-20261031'
DS=Path('C:/Users/bombe/OneDrive/Documents/ChatGPT/Ruang Kamare/roomscan-reconstruction/data/20261031_OSMO360/clean-v3/explicit-full-v1/dataset')
def ply(path):
    types={'float':'<f4','float32':'<f4','double':'<f8','uchar':'u1','uint8':'u1','int':'<i4','uint':'<u4'}
    fields=[];count=None
    with path.open('rb') as f:
        while True:
            line=f.readline().decode('ascii').strip()
            if line.startswith('element vertex '):count=int(line.split()[-1])
            if line.startswith('property '):
                _,kind,name=line.split();fields.append((name,types[kind]))
            if line=='end_header':break
        offset=f.tell()
    return np.memmap(path,dtype=np.dtype(fields),mode='r',offset=offset,shape=(count,))
if __name__=='__main__':
    cloud=ply(DS/'seed-dense-train.ply');xyz=np.stack([cloud[n] for n in ['x','y','z']],axis=1)
    xyz=xyz[np.isfinite(xyz).all(axis=1)];q=np.percentile(xyz,[1,2,5,50,95,98,99],axis=0)
    poses=json.loads((OLD/'review/clean-cameras-registered-poses.json').read_text())['poses']
    centers=np.asarray([p['position'] for p in poses]);lo=q[0].copy();hi=q[-1].copy()
    lo=np.minimum(lo,centers.min(axis=0));hi=np.maximum(hi,centers.max(axis=0))
    occupied=xyz[np.all((xyz>=lo)&(xyz<=hi),axis=1)]
    # Horizontal surfaces give concentrated Y support. Report the candidates;
    # do not silently assume a metric room height or a low furniture cut.
    hist,edges=np.histogram(occupied[:,1],bins=240,range=(lo[1],hi[1]));smooth=np.convolve(hist,[1,2,3,2,1],mode='same')
    mids=(edges[:-1]+edges[1:])/2;camera_low=np.percentile(centers[:,1],5);camera_high=np.percentile(centers[:,1],95)
    floor_i=np.flatnonzero(mids<camera_low);ceiling_i=np.flatnonzero(mids>max(camera_high+.6,np.percentile(occupied[:,1],85)))
    floor=float(mids[floor_i[np.argmax(smooth[floor_i])]]);ceiling=float(mids[ceiling_i[np.argmax(smooth[ceiling_i])]])
    sampled=occupied[np.linspace(0,len(occupied)-1,min(10000,len(occupied)),dtype=int)]
    normals=np.stack([cloud[n] for n in ['nx','ny','nz']],axis=1)
    def fit_horizontal(height):
        use=(np.abs(xyz[:,1]-height)<.13)&(np.abs(normals[:,1])>.88)
        points=xyz[use]
        if len(points)<500:raise ValueError('Insufficient horizontal evidence for a structural plane')
        design=np.column_stack([points[:,0],points[:,2],np.ones(len(points))]);keep=np.ones(len(points),bool)
        for _ in range(6):
            coef=np.linalg.lstsq(design[keep],points[keep,1],rcond=None)[0];residual=points[:,1]-design@coef;keep=np.abs(residual)<max(.02,2.5*np.median(np.abs(residual)))
        return {'YequalsAXplusBZplusC':coef.tolist(),'points':len(points),'inliers':int(keep.sum()),'rmseSceneUnits':float(np.sqrt(np.mean(residual[keep]**2))),'normalYUp':(np.array([-coef[0],1,-coef[1]])/np.linalg.norm([-coef[0],1,-coef[1]])).tolist()}
    plane_audit={'floor':fit_horizontal(floor),'upperCeiling':fit_horizontal(ceiling)}
    cameras=json.loads((OLD/'review/clean-cameras.json').read_text())
    # A convex footprint supplies boundary planes, not a horizontal wall-height cut.
    points=sorted(set(map(tuple,sampled[:,[0,2]].round(3).tolist())))
    def cross(o,a,b):return (a[0]-o[0])*(b[1]-o[1])-(a[1]-o[1])*(b[0]-o[0])
    lower=[];upper=[]
    for p in points:
        while len(lower)>=2 and cross(lower[-2],lower[-1],p)<=0:lower.pop()
        lower.append(p)
    for p in reversed(points):
        while len(upper)>=2 and cross(upper[-2],upper[-1],p)<=0:upper.pop()
        upper.append(p)
    hull=np.asarray(lower[:-1]+upper[:-1]);planes=[]
    for p,end in zip(hull,np.roll(hull,-1,axis=0)):
        delta=end-p;normal=np.array([delta[1],-delta[0]]);normal/=np.linalg.norm(normal)
        planes.append([float(normal[0]),float(normal[1]),float(normal@p)])
    cameras.update(bounds=[lo.tolist(),hi.tolist()],boundsSource='p01-p99 validated dense train seed, expanded to registered camera centers',framingPoints=sampled.round(5).reshape(-1).tolist(),occupiedShell={'floorY':floor,'ceilingY':ceiling,'ceilingBand':.18,'bounds':[lo.tolist(),hi.tolist()],'perimeterPlanes':planes,'perimeterBand':.10,'floorCeilingMethod':'Y-density mode below camera envelope, ceiling mode in upper occupied-height band; projection reviewed'})
    cameras['occupiedShell']['interiorCameras']=centers[np.linspace(0,len(centers)-1,32,dtype=int)].round(6).tolist()
    cameras['occupiedShell']['fittedPlanes']=plane_audit
    (W/'review/occupied-cameras.json').write_text(json.dumps(cameras,indent=2))
    report={'source':str(DS/'seed-dense-train.ply'),'sha256':hashlib.sha256((DS/'seed-dense-train.ply').read_bytes()).hexdigest(),'points':len(xyz),'quantileLevels':[1,2,5,50,95,98,99],'quantiles':q.tolist(),'bounds':[lo.tolist(),hi.tolist()],'cameraRange':[centers.min(axis=0).tolist(),centers.max(axis=0).tolist()],'floorY':floor,'ceilingY':ceiling,'fittedPlanes':plane_audit,'heightSpan':float(hi[1]-lo[1]),'heightUnits':'normalized scene units, not surveyed metres','sampledFramingPoints':len(sampled),'yHistogram':{'edges':edges.tolist(),'counts':hist.tolist()}}
    (W/'occupied-bounds-audit.json').write_text(json.dumps(report,indent=2))
    im=Image.new('RGB',(1600,900),'#17222e');d=ImageDraw.Draw(im)
    for axis,(u,v,title) in enumerate([(0,2,'Top X/Z'),(0,1,'Front X/Y'),(2,1,'Side Z/Y')]):
        ox=30+axis*525;oy=80;ww=490;hh=720
        d.text((ox,30),title,fill='white')
        for p in sampled:
            x=ox+int((p[u]-lo[u])/(hi[u]-lo[u])*ww);y=oy+hh-int((p[v]-lo[v])/(hi[v]-lo[v])*hh)
            d.point((x,y),fill='#b0c9cb')
        for p in centers:
            x=ox+int((p[u]-lo[u])/(hi[u]-lo[u])*ww);y=oy+hh-int((p[v]-lo[v])/(hi[v]-lo[v])*hh);d.ellipse((x-2,y-2,x+2,y+2),fill='#edb154')
        if v==1:
            for val,col in [(floor,'#57dfa0'),(ceiling,'#f47d87')]:
                y=oy+hh-int((val-lo[v])/(hi[v]-lo[v])*hh);d.line((ox,y,ox+ww,y),fill=col,width=2)
    im.save(W/'review/occupied-bounds.png')
    print(json.dumps({k:v for k,v in report.items() if k not in ['yHistogram']},indent=2))
