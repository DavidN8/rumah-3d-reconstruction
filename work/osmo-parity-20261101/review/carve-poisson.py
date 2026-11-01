"""Remove Poisson closures contradicted by >=5 distinct trusted timestamps.

A single positive surface observation protects a face. No height slicing,
no camera-space depth/range confusion and no count inflation from cube faces.
"""
from pathlib import Path
import sys,json,time
import numpy as np
W=Path(__file__).resolve().parent;ROOT=W.parent.parent
sys.path[:0]=[str(W.parent/'tsdfdeps'),str(ROOT/'osmo-improve-20261031/pydeps'),str(ROOT/'osmo-reconstruct-20261031')]
import cv2,moderngl
from seed_fisheye import read_model,qvec_to_rotmat
CAP=Path('C:/Users/bombe/OneDrive/Documents/ChatGPT/Ruang Kamare/roomscan-reconstruction/data/20261031_OSMO360');DS=CAP/'clean-v3/explicit-full-v1/dataset';OUT=W/'poisson-pilot'
if (OUT/'surface-carved.npz').exists():raise FileExistsError('Preserve prior carving')
started=time.monotonic();data=np.load(OUT/'surface.npz');v=data['positions'];f=data['faces'];n=data['normals'];p=v[f].mean(axis=1);N=len(p)
ctx=moderngl.create_standalone_context(require=430);positions=ctx.buffer(np.column_stack([p,np.ones(N)]).astype('f4').tobytes());positions.bind_to_storage_buffer(0);seen=ctx.buffer(reserve=N*8*4);seen.clear();seen.bind_to_storage_buffer(1);surface=ctx.buffer(reserve=N*4);surface.clear();surface.bind_to_storage_buffer(2)
shader=ctx.compute_shader('''#version 430
layout(local_size_x=256)in;
layout(std430,binding=0)readonly buffer Positions{vec4 pos[];};
layout(std430,binding=1)buffer Seen{uint bits[];};
layout(std430,binding=2)buffer Surface{uint match[];};
uniform usampler2D ranges;uniform mat3 R;uniform vec3 t;uniform vec4 K;uniform ivec2 size;uniform uint count,word,bitmask;
void main(){uint id=gl_GlobalInvocationID.x;if(id>=count)return;vec3 pc=R*pos[id].xyz+t;if(pc.z<=.02)return;
 ivec2 uv=ivec2(floor(pc.xy/pc.z*K.xy+K.zw+vec2(.5)));if(any(lessThan(uv,ivec2(0)))||any(greaterThanEqual(uv,size)))return;
 float observed=float(texelFetch(ranges,uv,0).r)*.001;if(observed<=0.)return;float delta=observed-length(pc);float tol=.035+.04*observed;
 if(abs(delta)<=tol)atomicOr(match[id],1u);else if(delta>tol)atomicOr(bits[id*8u+word],bitmask);
}''');shader['ranges'].value=0;shader['count'].value=N
cams,images,_=read_model(DS/'sparse/0');provenance=json.loads((DS/'explicit-pinhole-audit.json').read_text());lookup={x['name']:x for x in provenance['views']};timestamp_ids={};used=[]
for im in images.values():
    file=(DS/'depths-trusted'/im['name']).with_suffix('.png')
    if not file.exists():continue
    meta=lookup[im['name']]
    if meta['sourceSplit']!='train':raise ValueError('Evaluation map in carve')
    time_id=timestamp_ids.setdefault(meta['sourceFrame'],len(timestamp_ids));assert time_id<256
    raw=cv2.imread(str(file),cv2.IMREAD_UNCHANGED);h,w=raw.shape;c=cams[im['camera_id']];K=c['params']*np.array([w/c['width'],h/c['height'],w/c['width'],h/c['height']]);R=qvec_to_rotmat(im['qvec']);tex=ctx.texture((w,h),1,raw.tobytes(),dtype='u2');tex.use(0)
    shader['R'].write(np.asarray(R.T,'f4').tobytes());shader['t'].value=tuple(im['tvec']);shader['K'].value=tuple(K);shader['size'].value=(w,h);shader['word'].value=time_id//32;shader['bitmask'].value=1<<(time_id%32);shader.run((N+255)//256);ctx.memory_barrier();tex.release();used.append(im['name'])
    if len(used)%100==0:print('Free-space validation',len(used),'/439',flush=True)
ctx.finish();bits=np.frombuffer(seen.read(),dtype='u4').reshape(N,8);counts=np.bitwise_count(bits).sum(axis=1);match=np.frombuffer(surface.read(),dtype='u4')>0;drop=(counts>=5)&(~match);faces=f[~drop];unique,remap=np.unique(faces,return_inverse=True)
np.savez_compressed(OUT/'surface-carved.npz',positions=v[unique],normals=n[unique],faces=remap.reshape(-1,3).astype('u4'));np.savez_compressed(OUT/'carve-evidence.npz',distinct_free_timestamps=counts,surface_match=match,removed=drop)
report={'inputFaces':N,'removedFaces':int(drop.sum()),'retainedFaces':len(faces),'rule':'>=5 distinct train timestamps say face is in free space; no map says it is on a measured surface','rangeTolerance':'.035 + .04 * observed Euclidean ray range, unchanged scene units','trainMaps':len(used),'distinctTimestamps':len(timestamp_ids),'heldoutUsed':False,'heightClip':False,'seconds':time.monotonic()-started,'renderer':ctx.info['GL_RENDERER'],'status':'local pilot requires photographic and dollhouse inspection'}
(OUT/'carve-audit.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
