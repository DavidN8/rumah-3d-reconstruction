"""CPU, read-only geometry boundary audit of native source GLB (not meshopt-packed)."""
from pathlib import Path
import argparse,json,struct,time
import numpy as np

parser=argparse.ArgumentParser();parser.add_argument('--mesh',type=Path,default=Path(r'C:\Users\bombe\OneDrive\Documents\ChatGPT\Ruang Kamare\roomscan-reconstruction\data\20261031_OSMO360\lite-v1\exports\osmo-lite-trusted-source.glb'));args=parser.parse_args()
started=time.monotonic();raw=args.mesh.read_bytes();magic,version,size=struct.unpack_from('<III',raw)
assert magic==0x46546c67 and version==2 and size==len(raw)
n,k=struct.unpack_from('<II',raw,12);g=json.loads(raw[20:20+n]);bin_off=20+n+8
assert len(g['meshes'])==1 and len(g['meshes'][0]['primitives'])==1
p=g['meshes'][0]['primitives'][0]
def accessor(index):
    a=g['accessors'][index];v=g['bufferViews'][a['bufferView']]
    if v.get('extensions'):raise ValueError('Use native source GLB, not compressed asset')
    dtypes={5126:'<f4',5125:'<u4',5123:'<u2',5122:'<i2'};count={'SCALAR':1,'VEC3':3}
    if v.get('byteStride',np.dtype(dtypes[a['componentType']]).itemsize*count[a['type']])!=np.dtype(dtypes[a['componentType']]).itemsize*count[a['type']]:raise ValueError('Interleaved accessor unsupported')
    return np.frombuffer(raw,dtype=dtypes[a['componentType']],count=a['count']*count[a['type']],offset=bin_off+v.get('byteOffset',0)+a.get('byteOffset',0)).reshape(-1,count[a['type']])
xyz0=accessor(p['attributes']['POSITION']);faces=accessor(p['indices']).reshape(-1,3)
print(f'Loaded {len(xyz0):,} UV vertices / {len(faces):,} faces',flush=True)
# Exact coordinate welding only removes texture seam duplicates; no geometry moves.
xyz,inverse=np.unique(xyz0,axis=0,return_inverse=True)
faces=inverse[faces]
aa=np.concatenate([faces[:,0],faces[:,1],faces[:,2]]).astype(np.uint64)
bb=np.concatenate([faces[:,1],faces[:,2],faces[:,0]]).astype(np.uint64)
lo=np.minimum(aa,bb);hi=np.maximum(aa,bb);keys=(lo<<np.uint64(32))|hi
unique,counts=np.unique(keys,return_counts=True);boundary=unique[counts==1]
edges=np.column_stack([boundary>>np.uint64(32),boundary&np.uint64(0xffffffff)]).astype(np.int64)
adj={}
for a,b in edges:
    adj.setdefault(int(a),[]).append(int(b));adj.setdefault(int(b),[]).append(int(a))
visited=set();loops=[];ambiguous=0
for a0,b0 in edges:
    a0,b0=int(a0),int(b0);key=(min(a0,b0),max(a0,b0))
    if key in visited:continue
    if len(adj[a0])!=2 or len(adj[b0])!=2:
        visited.add(key);ambiguous+=1;continue
    loop=[a0];prev=a0;cur=b0;valid=True
    while cur!=a0:
        visited.add((min(prev,cur),max(prev,cur)));loop.append(cur)
        if len(adj[cur])!=2 or len(loop)>len(edges):valid=False;break
        nxt=adj[cur][0] if adj[cur][0]!=prev else adj[cur][1]
        if (min(cur,nxt),max(cur,nxt)) in visited and nxt!=a0:valid=False;break
        prev,cur=cur,nxt
    if not valid:ambiguous+=1;continue
    visited.add((min(prev,cur),max(prev,cur)))
    pts=xyz[loop];center=pts.mean(0);_,_,vh=np.linalg.svd(pts-center,full_matrices=False)
    distance=(pts-center)@vh[-1]
    loops.append({'edges':len(loop),'bbox_diagonal':float(np.linalg.norm(pts.max(0)-pts.min(0))),
                  'perimeter':float(np.linalg.norm(pts-np.roll(pts,1,axis=0),axis=1).sum()),
                  'plane_rms':float(np.sqrt(np.mean(distance**2))),'plane_max':float(np.max(np.abs(distance))),
                  'center':center.tolist(),'normal':vh[-1].tolist()})
def summary(sub):
    return {'loops':len(sub),'max_diameter':max([r['bbox_diagonal'] for r in sub],default=0),
            'diameter_p50':float(np.median([r['bbox_diagonal'] for r in sub])) if sub else 0,
            'over_0_25_units':sum(r['bbox_diagonal']>.25 for r in sub),'over_0_50_units':sum(r['bbox_diagonal']>.5 for r in sub)}
report={'source':str(args.mesh),'mesh_mutated':False,'units':'Approximate normalized world units, using assumed1.5m median camera height',
        'uv_vertices':len(xyz0),'position_welded_vertices':len(xyz),'faces':len(faces),'boundary_edges_after_uv_seam_welding':len(edges),
        'nonmanifold_edges_after_position_welding':int((counts>2).sum()),'ambiguous_boundary_paths':ambiguous,
        'simple_closed_boundary_loops':len(loops),'edge_count_bands':{name:summary([r for r in loops if test(r['edges'])]) for name,test in [('<=12',lambda n:n<=12),('13..32',lambda n:12<n<=32),('33..64',lambda n:32<n<=64),('>64',lambda n:n>64)]},
        'largest_loops_with_up_to64_edges':sorted([r for r in loops if r['edges']<=64],key=lambda r:r['bbox_diagonal'],reverse=True)[:15],
        'small_planar_repair_candidates':sum(r['bbox_diagonal']<=.05 and r['plane_max']<=.005 for r in loops),
        'elapsed_seconds':time.monotonic()-started}
out=Path(__file__).parent/'boundary-audit.json';out.write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
