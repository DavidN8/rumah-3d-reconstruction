"""Fuse only validated, train-only Euclidean ray ranges; preserve world scale."""
from pathlib import Path
import json,sys,time,hashlib
import numpy as np
W=Path(__file__).resolve().parent;ROOT=W.parent.parent
sys.path[:0]=[str(W.parent/'tsdfdeps'),str(ROOT/'osmo-improve-20261031/pydeps'),str(ROOT/'osmo-reconstruct-20261031')]
import cv2,moderngl
from scipy.ndimage import gaussian_filter,map_coordinates
from skimage.measure import marching_cubes
from seed_fisheye import read_model,qvec_to_rotmat
CAP=Path('C:/Users/bombe/OneDrive/Documents/ChatGPT/Ruang Kamare/roomscan-reconstruction/data/20261031_OSMO360');DS=CAP/'clean-v3/explicit-full-v1/dataset';OUT=W/'tsdf-pilot';OUT.mkdir(exist_ok=True)
if (OUT/'surface.npz').exists():raise FileExistsError(OUT/'surface.npz')
started=time.monotonic();metadata=json.loads((W/'occupied-cameras.json').read_text());bounds=np.array(metadata['bounds']);origin=bounds[0]-.22;voxel=.025;dims=np.ceil((bounds[1]+.22-origin)/voxel).astype(int);shape=tuple(map(int,dims[::-1]));size=int(np.prod(dims))
ctx=moderngl.create_standalone_context(require=430);zeros=np.zeros(size,'f4').tobytes();sums=ctx.texture3d(tuple(map(int,dims)),1,zeros,dtype='f4');weights=ctx.texture3d(tuple(map(int,dims)),1,zeros,dtype='f4');sums.bind_to_image(0,read=True,write=True);weights.bind_to_image(1,read=True,write=True)
shader='''#version 430
layout(local_size_x=8,local_size_y=8,local_size_z=4)in;
layout(r32f,binding=0)uniform image3D sums;
layout(r32f,binding=1)uniform image3D weights;
uniform usampler2D ranges;
uniform mat3 R;uniform vec3 t,origin;uniform vec4 K;uniform ivec3 dims;uniform ivec2 depthSize;uniform float voxel,mu;
void main(){
 ivec3 cell=ivec3(gl_GlobalInvocationID);if(any(greaterThanEqual(cell,dims)))return;
 vec3 p=origin+(vec3(cell)+0.5)*voxel;vec3 pc=R*p+t;if(pc.z<=0.02)return;
 ivec2 uv=ivec2(floor(pc.xy/pc.z*K.xy+K.zw+vec2(0.5)));
 if(any(lessThan(uv,ivec2(0)))||any(greaterThanEqual(uv,depthSize)))return;
 float measured=float(texelFetch(ranges,uv,0).r)*0.001;if(measured<=0.0)return;
 // Stored depths are Euclidean ray ranges, never pinhole Z depths.
 float delta=measured-length(pc);if(delta < -mu)return;
 float value=clamp(delta/mu,-1.0,1.0);
 float sum=imageLoad(sums,cell).r,weight=imageLoad(weights,cell).r;
 imageStore(sums,cell,vec4(sum+value));imageStore(weights,cell,vec4(weight+1.0));
}'''
compute=ctx.compute_shader(shader);compute['origin'].value=tuple(origin);compute['dims'].value=tuple(map(int,dims));compute['voxel'].value=voxel;compute['mu'].value=4*voxel;compute['ranges'].value=2
cameras,images,_=read_model(DS/'sparse/0');views=[];provenance=json.loads((DS/'explicit-pinhole-audit.json').read_text());lookup={v['name']:v for v in provenance['views']}
for im in images.values():
    file=(DS/'depths-trusted'/im['name']).with_suffix('.png')
    if not file.exists():continue
    if lookup[im['name']]['sourceSplit']!='train':raise ValueError('Evaluation geometry attempted to enter fusion')
    raw=cv2.imread(str(file),cv2.IMREAD_UNCHANGED)
    if raw.dtype!=np.uint16:raise ValueError('Expected encoded ray range')
    h,w=raw.shape;camera=cameras[im['camera_id']];R=qvec_to_rotmat(im['qvec']);K=camera['params']*np.array([w/camera['width'],h/camera['height'],w/camera['width'],h/camera['height']])
    tex=ctx.texture((w,h),1,raw.tobytes(),dtype='u2');tex.use(2);compute['R'].write(np.asarray(R.T,'f4').tobytes());compute['t'].value=tuple(im['tvec']);compute['K'].value=tuple(K);compute['depthSize'].value=(w,h)
    compute.run((int(dims[0])+7)//8,(int(dims[1])+7)//8,(int(dims[2])+3)//4);ctx.memory_barrier();tex.release();views.append(im['name'])
    if len(views)%40==0:ctx.finish();print(f'TSDF {len(views)}/439 views; {time.monotonic()-started:.1f}s',flush=True)
ctx.finish();acc=np.frombuffer(sums.read(),dtype='f4').reshape(shape);weight=np.frombuffer(weights.read(),dtype='f4').reshape(shape);volume=np.ones(shape,'f4');valid=weight>=3;volume[weight>0]=acc[weight>0]/weight[weight>0]
# Smooth the fused signed field within supported voxels, at half a voxel only.
numerator=gaussian_filter(volume*np.minimum(weight,3),.5);denominator=gaussian_filter(np.minimum(weight,3),.5);volume[valid]=numerator[valid]/np.maximum(denominator[valid],1e-8)
print('Extracting supported zero surface',flush=True);verts,faces,_,_=marching_cubes(volume,0,mask=valid,allow_degenerate=False)
gradient=np.gradient(volume);g=np.stack([map_coordinates(axis,verts.T,order=1,mode='nearest') for axis in gradient],axis=1)[:,::-1].copy();g/=np.maximum(np.linalg.norm(g,axis=1,keepdims=True),1e-12)
xyz=(verts[:,::-1]+.5)*voxel+origin;faces=faces.astype('u4');face_normal=np.cross(xyz[faces[:,1]]-xyz[faces[:,0]],xyz[faces[:,2]]-xyz[faces[:,0]]);target=g[faces].mean(axis=1);flip=np.sum(face_normal*target,axis=1)<0;faces[flip]=faces[flip][:,[0,2,1]]
np.savez_compressed(OUT/'surface.npz',positions=xyz.astype('f4'),normals=g.astype('f4'),faces=faces)
audit={'sourceDataset':str(DS),'sourceDepthAuditSha256':hashlib.sha256((DS/'trusted-depth-and-seed-audit.json').read_bytes()).hexdigest(),'method':'Train-only cross-time-validated Euclidean range TSDF; no Gaussian checkpoint surface, no affine alignment, no synthesized photographs','views':len(views),'sourceFrames':len({lookup[v]['sourceFrame'] for v in views}),'evalUsed':False,'worldFrame':'+Y up, unchanged normalized scene units','voxelSceneUnits':voxel,'truncationSceneUnits':4*voxel,'dimensionsXYZ':dims.tolist(),'minimumViewContributions':3,'eachInputPixelAlreadyValidatedAgainstOtherTimes':True,'heightClipping':False,'smoothingSigmaVoxels':.5,'vertices':len(xyz),'faces':len(faces),'renderer':ctx.info['GL_RENDERER'],'seconds':time.monotonic()-started,'viewsUsed':views}
(OUT/'fusion-audit.json').write_text(json.dumps(audit,indent=2));print(json.dumps({k:v for k,v in audit.items() if k!='viewsUsed'},indent=2))
