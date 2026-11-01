"""Shared frame/GLB math. Column-vector convention: p' = s R p + t."""
import json
import struct
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation

BASE = Path(__file__).resolve().parents[1]


def read_glb(path):
    with Path(path).open('rb') as f:
        magic, version, size = struct.unpack('<III', f.read(12))
        assert magic == 0x46546C67 and version == 2
        n, kind = struct.unpack('<II', f.read(8)); assert kind == 0x4E4F534A
        doc = json.loads(f.read(n))
        n, kind = struct.unpack('<II', f.read(8)); assert kind == 0x004E4942
        binary = bytearray(f.read(n)); assert f.tell() == size
    return doc, binary


def accessor(doc, binary, i, copy=True):
    a = doc['accessors'][i]; v = doc['bufferViews'][a['bufferView']]
    dt = np.dtype({5126:'<f4',5125:'<u4',5123:'<u2',5122:'<i2',5121:'u1'}[a['componentType']])
    width = {'SCALAR':1,'VEC2':2,'VEC3':3,'VEC4':4,'MAT4':16}[a['type']]
    arr = np.ndarray((a['count'],width), dtype=dt, buffer=binary,
                     offset=v.get('byteOffset',0)+a.get('byteOffset',0),
                     strides=(v.get('byteStride',dt.itemsize*width),dt.itemsize))
    return arr.copy() if copy else arr


def write_glb(path, doc, binary):
    while len(binary)%4:
        binary.append(0)
    doc['buffers'] = [{'byteLength':len(binary)}]
    j=json.dumps(doc,separators=(',',':'),ensure_ascii=False).encode('utf-8')
    j+=b' '*((-len(j))%4)
    path=Path(path); temp=path.with_suffix('.tmp.glb')
    with temp.open('wb') as f:
        f.write(struct.pack('<III',0x46546C67,2,12+8+len(j)+8+len(binary)))
        f.write(struct.pack('<II',len(j),0x4E4F534A));f.write(j)
        f.write(struct.pack('<II',len(binary),0x004E4942));f.write(binary)
    temp.replace(path)


def proper_rotation(a,b):
    a=np.asarray(a,dtype=float); a/=np.linalg.norm(a)
    b=np.asarray(b,dtype=float); b/=np.linalg.norm(b)
    cross=np.cross(a,b); sine=np.linalg.norm(cross); cosine=np.clip(a@b,-1,1)
    if sine<1e-10:
        if cosine>0:return np.eye(3)
        axis=np.cross(a,[1.,0,0] if abs(a[0])<.8 else [0.,0,1]);axis/=np.linalg.norm(axis)
        return Rotation.from_rotvec(np.pi*axis).as_matrix()
    return Rotation.from_rotvec(cross/sine*np.arctan2(sine,cosine)).as_matrix()


def mesh_arrays(path):
    d,b=read_glb(path)
    # Spirula emits identity mesh nodes; reject an unhandled source transform.
    for n in d['nodes']:
        if 'matrix' in n: assert np.allclose(np.array(n['matrix']).reshape(4,4),np.eye(4))
        assert 'rotation' not in n and 'translation' not in n and 'scale' not in n
    p=d['meshes'][0]['primitives'][0]
    return accessor(d,b,p['attributes']['POSITION']).astype(float),accessor(d,b,p['indices']).reshape(-1,3)


def fit_floor(vertices, triangles, up, camera_centres, ceiling=False):
    rng=np.random.default_rng(625)
    # Surface-area sampling avoids bias toward highly subdivided furniture.
    t=vertices[triangles]; cross=np.cross(t[:,1]-t[:,0],t[:,2]-t[:,0]);area=np.linalg.norm(cross,axis=1)
    normal=cross/np.maximum(area[:,None],1e-12); center=t.mean(1);h=center@up
    ch=np.median(camera_centres@up)
    horizontal=np.abs(normal@up)>.94
    mask=horizontal & (h>ch+.10 if ceiling else h<ch-.12)
    if not ceiling:
        # Each component has its own datum. In particular the kitchen floor is
        # near -0.42 in the OLD joined frame, while its countertop is near zero.
        # Select the dominant low horizontal SURFACE AREA, not a zero-height
        # prior or the dense vertices on cabinets.
        hist,edges=np.histogram(h[mask],bins=np.arange(h[mask].min()-.001,h[mask].max()+.021,.02),weights=area[mask])
        peak=np.flatnonzero(hist>=hist.max()*.25)[0];mode=(edges[peak]+edges[peak+1])/2
        mask &= np.abs(h-mode)<.035
    else:
        mask &= h < 1.1
    candidates=np.flatnonzero(mask & (area>1e-12))
    if len(candidates)<30:raise ValueError('insufficient horizontal floor/ceiling geometry')
    weights=area[candidates];weights/=weights.sum()
    sample=rng.choice(candidates,min(12000,len(candidates)),replace=False,p=weights)
    p=center[sample]; w=area[sample]; best=None
    for _ in range(1200):
        k=rng.choice(len(p),3,replace=False); n=np.cross(p[k[1]]-p[k[0]],p[k[2]]-p[k[0]])
        norm=np.linalg.norm(n)
        if norm<1e-10:continue
        n/=norm;n=n if n@up>0 else -n
        if n@up<.985:continue
        level=p[k[0]]@n; ds=np.abs(p@n-level); keep=ds<.005
        score=w[keep].sum()
        if best is None or score>best[0]:best=score,n,level,keep
    _,n,level,keep=best
    for _ in range(4):
        pp=p[keep];ww=w[keep];mu=np.average(pp,axis=0,weights=ww)
        _,v=np.linalg.eigh(((pp-mu)*ww[:,None]).T@(pp-mu));n=v[:,0];n=n if n@up>0 else -n
        level=mu@n; keep=np.abs(p@n-level)<.005
    return dict(normal=n.tolist(),offset=float(level),rms_units=float(np.sqrt(np.average((p[keep]@n-level)**2,weights=w[keep]))),
                inlier_area_units2=float(w[keep].sum()/2),camera_heights_units=(camera_centres@n-level).tolist())


def apply_sim(points,rec):
    return rec['scale']*np.asarray(points)@np.array(rec['R']).T+np.array(rec['t'])


def view_support_distances(points, poses):
    """Nearest camera in each zone that actually faces the surface (GPU).

    A nearby camera looking at another wall cannot own a bed or cabinet it
    never saw. A generous frustum margin preserves borders and ceilings.
    """
    import torch
    assert torch.cuda.is_available(), 'GPU camera support computation required'
    p=torch.as_tensor(points,dtype=torch.float32,device='cuda')
    scores=torch.full((3,len(p)),float('inf'),dtype=torch.float32,device='cuda')
    with torch.inference_mode():
        for start in range(0,len(poses),32):
            batch=poses[start:start+32]
            r=torch.tensor(np.array([v['R'] for v in batch]),dtype=torch.float32,device='cuda')
            t=torch.tensor(np.array([v['t'] for v in batch]),dtype=torch.float32,device='cuda')
            pc=torch.einsum('nij,mj->nmi',r,p)+t[:,None,:]
            z=pc[:,:,2]
            seen=(z>.025)&(pc[:,:,0].abs()<z*.72)&(pc[:,:,1].abs()<z*1.25)
            distance=torch.linalg.vector_norm(pc,dim=2).masked_fill(~seen,float('inf'))
            for zone in range(3):
                indices=[i for i,v in enumerate(batch) if v['zone']==zone]
                if indices:scores[zone]=torch.minimum(scores[zone],distance[indices].min(0).values)
    result=scores.cpu().numpy()
    return result
