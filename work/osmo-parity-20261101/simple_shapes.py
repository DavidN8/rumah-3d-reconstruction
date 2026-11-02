"""Simple-shape stand-in for the Osmo room: floor and ceiling slabs, walls, and one
box, cylinder or sphere per object, each coloured from the splats it replaces.

Walls are snapped to the room's dominant (Manhattan) direction and found where opaque
vertical splats cover most of the wall height, so door and window gaps stay open.
Objects are connected opaque voxels between floor and ceiling, away from walls.
The output is a small JSON the viewer turns into three.js primitives.

Usage: python -B simple_shapes.py MODEL.ply review/calibrated-occupied-cameras.json review/simple-shapes.json
"""
from pathlib import Path
import base64,hashlib,json,math,sys
import cv2,numpy as np
from scipy import ndimage
from occupied_bounds import ply
from occupied_footprint import normals

CELL=.05            # grid/voxel size in scene units
WALL_COVER=.6       # share of 0.3-2.0 height bins a wall cell must fill
WALL_RUN=.5         # shortest straight wall piece
MIN_CELLS=12        # smallest object footprint kept (0.03 square units)
BAND=.3             # neighbouring cells join one object only if their tops share a band
MAX_OBJECTS=400

def sigmoid(v):return 1/(1+np.exp(-v))
def hexcolor(rgb):return '#'+''.join(f'{int(round(float(v)*255)):02x}' for v in np.clip(rgb,0,1))
def largest_rectangles(mask,min_cells):
    # Greedy maximal all-true rectangles (histogram method) until the rest is too small.
    mask=mask.copy();out=[]
    while True:
        best=(0,None);heights=np.zeros(mask.shape[1],int)
        for r in range(mask.shape[0]):
            heights=np.where(mask[r],heights+1,0);stack=[]
            for k in range(len(heights)+1):
                h=heights[k] if k<len(heights) else 0;start=k
                while stack and stack[-1][1]>=h:
                    start,hh=stack.pop();area=hh*(k-start)
                    if area>best[0]:best=(area,(r-hh+1,start,r+1,k))
                stack.append((start,h))
        if best[0]<min_cells:return out
        r0,c0,r1,c1=best[1];mask[r0:r1,c0:c1]=False;out.append(best[1])

def shapes(model,shell):
    fp=shell['footprint'];W,H=fp['size'];c=fp['cellSize'];o=fp['origin']
    sdf=np.frombuffer(base64.b64decode(fp['sdfCm']),np.int8).reshape(W,H)/100
    low=np.frombuffer(base64.b64decode(fp['lowerCeiling']['select']),np.uint8).reshape(W,H).astype(bool) if fp.get('lowerCeiling') else np.zeros((W,H),bool)
    planes=[shell['fittedPlanes']['floor']['YequalsAXplusBZplusC'],shell['fittedPlanes']['upperCeiling']['YequalsAXplusBZplusC'],(fp.get('lowerCeiling') or shell['fittedPlanes']['upperCeiling'])['YequalsAXplusBZplusC']]
    at=lambda p,x,z:p[0]*x+p[1]*z+p[2]
    cell=lambda x,z:(np.clip(((x-o[0])/c).astype(int),0,W-1),np.clip(((z-o[1])/c).astype(int),0,H-1))
    def ceiling(x,z):
        i,k=cell(x,z);return np.where(low[i,k],at(planes[2],x,z),at(planes[1],x,z))
    d=ply(Path(model));x,y,z=(d[k].astype(np.float64) for k in 'xyz');alpha=sigmoid(d['opacity'].astype(np.float64));n=normals(d)
    rgb=np.clip(.5+.28209479*np.stack([d['f_dc_0'],d['f_dc_1'],d['f_dc_2']],1),0,1)
    i,k=cell(x,z);dist=sdf[i,k];floor=at(planes[0],x,z);top=ceiling(x,z)
    # Manhattan direction from opaque vertical splats: average angle on the 4-fold circle.
    vertical=(alpha>.5)&(np.abs(n[:,1])<.2)&(dist<.15);phi=4*np.arctan2(n[vertical,2],n[vertical,0])
    theta=float(np.arctan2(np.sin(phi).sum(),np.cos(phi).sum())/4);ax=np.array([math.cos(theta),math.sin(theta)]);bx=np.array([-math.sin(theta),math.cos(theta)])
    u=x*ax[0]+z*ax[1];v=x*bx[0]+z*bx[1];inside=dist<=0
    u0,v0=u[inside].min()-.2,v[inside].min()-.2;U=int((u[inside].max()+.2-u0)/CELL)+1;V=int((v[inside].max()+.2-v0)/CELL)+1
    iu=np.clip(((u-u0)/CELL).astype(int),0,U-1);iv=np.clip(((v-v0)/CELL).astype(int),0,V-1)
    centre=lambda a,b:(u0+(a+.5)*CELL,v0+(b+.5)*CELL)
    world=lambda cu,cv:(cu*ax[0]+cv*bx[0],cu*ax[1]+cv*bx[1])
    au,av=np.meshgrid(np.arange(U),np.arange(V),indexing='ij');gx,gz=world(*centre(au,av));gi,gk=cell(gx,gz);room=sdf[gi,gk]<=0
    out=[];yaw=-theta  # three.js rotation.y that maps local +X onto the wall axis
    def add(kind,kind_type,cu,cv,y0,y1,su,sv,colour,**extra):
        wx,wz=world(cu,cv);out.append({'kind':kind,'type':kind_type,'center':[round(float(wx),3),round(float((y0+y1)/2),3),round(float(wz),3)],'size':[round(float(su),3),round(float(y1-y0),3),round(float(sv),3)],'yaw':round(yaw+extra.pop('turn',0.),4),'color':hexcolor(colour),**extra})
    flat=(alpha>.35)&(np.abs(n[:,1])>.85);floor_rgb=np.median(rgb[flat&(np.abs(y-floor)<.06)],0);ceil_rgb=np.median(rgb[flat&(np.abs(y-top)<.06)],0)
    # Walls: cells whose opaque vertical splats fill most height bins, split into straight u/v runs.
    bins=np.arange(.3,2.0,.1);wall_pts=(alpha>.4)&(np.abs(n[:,1])<.3)&(dist<.15)&(y>floor+.3)&(y<np.minimum(top-.15,floor+2.0))
    hb=np.clip(((y[wall_pts]-floor[wall_pts]-.3)/.1).astype(int),0,len(bins)-1);cover=np.zeros((U,V,len(bins)),bool);cover[iu[wall_pts],iv[wall_pts],hb]=True
    # A wall's splats spread over 2-3 cells of thickness; pool each height bin over 3x3 first.
    pooled=ndimage.maximum_filter(cover,size=(3,3,1)).mean(2);run=int(WALL_RUN/CELL)
    def runs(mask,axis):
        line=np.zeros((3,3),bool);line[(slice(None),1) if axis==0 else (1,slice(None))]=True;lab,_=ndimage.label(mask,structure=line)
        size=ndimage.sum(mask,lab,np.arange(lab.max()+1));return (size[lab]>=run)&mask
    wall_id=np.zeros((U,V),int);pieces=[]
    for axis in (0,1):
        lab,_=ndimage.label(runs(pooled>=WALL_COVER,axis))
        for j,sl in enumerate(ndimage.find_objects(lab),1):
            if (sl[axis].stop-sl[axis].start)<run:continue
            wall_id[sl][lab[sl]==j]=1;pieces.append((axis,sl,wall_pts&(lab[iu,iv]==j)))
    # Interior: footprint cells reachable from the capture path without crossing wall evidence.
    # Floor seen through glass or in a mirror lies beyond a wall and drops out here.
    lab,_=ndimage.label(room&~ndimage.binary_dilation(pooled>=.35,iterations=2));cams=np.asarray(shell['interiorCameras'])
    grid=lambda wx,wz:(np.clip(((wx*ax[0]+wz*ax[1]-u0)/CELL).astype(int),0,U-1),np.clip(((wx*bx[0]+wz*bx[1]-v0)/CELL).astype(int),0,V-1))
    reached=np.setdiff1d(lab[grid(cams[:,0],cams[:,2])],[0]);interior=ndimage.binary_dilation(np.isin(lab,reached),iterations=3)&room
    # Floor and ceiling slabs over the interior, as few rectangles as cover it. Ceilings are split
    # by level so no slab spans the dropped and the upper ceiling.
    slab=ndimage.binary_erosion(interior);dropped=low[gi,gk]
    for r0,c0,r1,c1 in largest_rectangles(slab,32):
        cu,cv=u0+(r0+r1)/2*CELL,v0+(c0+c1)/2*CELL;wx,wz=world(cu,cv);fy=float(at(planes[0],wx,wz))
        add('floor','box',cu,cv,fy-.04,fy,(r1-r0)*CELL,(c1-c0)*CELL,floor_rgb)
    for level in (slab&dropped,slab&~dropped):
        for r0,c0,r1,c1 in largest_rectangles(level,32):
            cu,cv=u0+(r0+r1)/2*CELL,v0+(c0+c1)/2*CELL;wx,wz=world(cu,cv);ty=float(ceiling(np.array([wx]),np.array([wz]))[0])
            add('ceiling','box',cu,cv,ty,ty+.04,(r1-r0)*CELL,(c1-c0)*CELL,ceil_rgb)
    wall_id[:]=0  # re-marked below with the final, thin wall boxes
    for axis,sl,mine in pieces:
        cu,cv=u0+(sl[0].start+sl[0].stop)/2*CELL,v0+(sl[1].start+sl[1].stop)/2*CELL;length=(sl[axis].stop-sl[axis].start)*CELL
        thick=(sl[1-axis].stop-sl[1-axis].start)*CELL;normal=bx if axis==0 else ax;extra={}
        # Exterior walls (interior on one side only) carry the outward direction the viewer cuts by.
        wx,wz=world(cu,cv);reach=thick/2+np.array([.15,.3,.6,.9,1.2])  # furniture in front can hide the room at one depth
        side=[bool(interior[grid(wx+k*reach*normal[0],wz+k*reach*normal[1])].any()) for k in (1,-1)]
        wall_t=min(max(thick,.1),.15)
        if side[0]!=side[1]:
            k=-1 if side[0] else 1;extra['outward']=[round(float(k*normal[0]),4),round(float(k*normal[1]),4)]
            # A band thicker than a wall is wall plus furniture: keep the wall flush with the outside.
            shift=k*max(thick-wall_t,0)/2;cu,cv=(cu,cv+shift) if axis==0 else (cu+shift,cv)
        su,sv=(length,wall_t) if axis==0 else (wall_t,length)
        a0,a1=int((cu-su/2-u0)/CELL),int(np.ceil((cu+su/2-u0)/CELL));b0,b1=int((cv-sv/2-v0)/CELL),int(np.ceil((cv+sv/2-v0)/CELL));wall_id[max(a0,0):a1,max(b0,0):b1]=1
        wx,wz=world(cu,cv);fy=float(at(planes[0],wx,wz));ty=float(ceiling(np.array([wx]),np.array([wz]))[0])
        add('wall','box',cu,cv,fy,ty,su,sv,np.median(rgb[mine],0) if mine.any() else ceil_rgb,**extra)
    # Objects (2.5D): per plan cell, the top run of opaque voxels between floor and ceiling,
    # away from walls. Neighbouring cells join only when their tops share a BAND, so a table
    # and what stands on it separate. Low pieces stand on the floor; raised ones keep their base.
    near_wall=ndimage.binary_dilation(wall_id>0,iterations=2)
    # Furniture against a wall is wall-like evidence too: grow the interior up to, never through, detected walls.
    reachable=ndimage.binary_dilation(interior,iterations=10,mask=room&(wall_id==0))
    keep=(alpha>.4)&inside&(dist<-.02)&(y>floor+.08)&(y<top-.12)&~near_wall[iu,iv]&reachable[iu,iv]
    Y=int(3/CELL)+1;iy=np.clip(((y-floor)/CELL).astype(int),0,Y-1);levels=np.arange(Y)
    mass=np.zeros((U,V,Y));np.add.at(mass,(iu[keep],iv[keep],iy[keep]),alpha[keep]);solid=mass>=1.
    column=solid.sum(2)>=2;top_i=np.where(solid,levels,-1).max(2)
    bridged=solid|np.roll(solid,1,2)&np.roll(solid,-1,2)  # one-voxel gaps do not end a run
    base_i=np.where(~bridged&(levels<top_i[...,None]),levels,-1).max(2)+1
    band=np.where(column,top_i*CELL//BAND+1,0).astype(int);pieces=[]
    for b in np.unique(band[band>0]):
        lab,_=ndimage.label(ndimage.binary_opening(band==b))  # opening cuts 1-2 cell bridges between items
        for j,sl in enumerate(ndimage.find_objects(lab),1):
            cells=np.argwhere(lab[sl]==j)+[sl[0].start,sl[1].start]
            if len(cells)>=MIN_CELLS:pieces.append(cells)
    pieces=sorted(pieces,key=len,reverse=True)[:MAX_OBJECTS];owner=np.zeros((U,V),int)
    for j,cells in enumerate(pieces,1):owner[cells[:,0],cells[:,1]]=j
    # Group splat indices by object once instead of scanning every splat per object.
    # Colour from each piece's own height run only, not from whatever stands underneath it.
    own=keep&(iy>=base_i[iu,iv])&(iy<=top_i[iu,iv]);point_owner=np.where(own,owner[iu,iv],0);idx=np.flatnonzero(point_owner);idx=idx[np.argsort(point_owner[idx],kind='stable')]
    labels,starts=np.unique(point_owner[idx],return_index=True)
    members={label:idx[a:b] for label,a,b in zip(labels,starts,np.append(starts[1:],len(idx)))}
    for j,cells in enumerate(pieces,1):
        (pcu,pcv),(wa,wb),ang=cv2.minAreaRect(cells.astype(np.float32));wa,wb=(wa+1)*CELL,(wb+1)*CELL;cu,cv=u0+(pcu+.5)*CELL,v0+(pcv+.5)*CELL
        tops,bases=top_i[cells[:,0],cells[:,1]],base_i[cells[:,0],cells[:,1]];lo=np.percentile(bases,10)*CELL;hi=(np.percentile(tops,90)+1)*CELL
        if lo<.4:lo=0.
        if hi-lo<.08:continue
        wx,wz=world(cu,cv);fy=float(at(planes[0],wx,wz));y0,y1=fy+lo,fy+hi;ht=y1-y0
        plan_fill=len(cells)*CELL*CELL/(wa*wb);solid_fill=float(np.clip(tops-bases+1,0,None).sum())*CELL**3/(wa*wb*ht)
        colour=np.median(rgb[members[j]],0) if j in members else ceil_rgb;turn=-math.radians(ang)
        if max(wa,wb,ht)/min(wa,wb,ht)<1.35 and .35<solid_fill<.7 and max(wa,wb,ht)<.7:
            dia=(wa+wb+ht)/3;add('object','sphere',cu,cv,y0,y0+dia,dia,dia,colour)
        elif max(wa,wb)/min(wa,wb)<1.3 and .6<plan_fill<.88:
            dia=(wa+wb)/2;add('object','cylinder',cu,cv,y0,y1,dia,dia,colour)
        else:add('object','box',cu,cv,y0,y1,wa,wb,colour,turn=turn)
    kinds={k:sum(s['kind']==k for s in out) for k in ['floor','ceiling','wall','object']}
    types={t:sum(s['type']==t for s in out) for t in ['box','cylinder','sphere']}
    return {'version':1,'units':'normalized scene units, +Y up; yaw is three.js rotation.y','manhattanYaw':round(theta,5),
        'source':{'file':Path(model).name,'sha256':hashlib.file_digest(open(model,'rb'),'sha256').hexdigest()},
        'counts':{**kinds,**types},'shapes':out}

if __name__=='__main__':
    if len(sys.argv)!=4:raise SystemExit(__doc__)
    model,cameras,output=sys.argv[1:]
    result=shapes(model,json.loads(Path(cameras).read_text())['occupiedShell'])
    Path(output).write_text(json.dumps(result,separators=(',',':')))
    print(json.dumps({k:v for k,v in result.items() if k!='shapes'},indent=1))
