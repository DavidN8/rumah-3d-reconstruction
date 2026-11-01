"""Independent ray-range plane and mask checks for the actual fusion shader."""
from pathlib import Path
import ast,json,sys
import numpy as np
W=Path(__file__).resolve().parent;sys.path.insert(0,str(W.parent.parent/'osmo-improve-20261031/pydeps'));import moderngl
tree=ast.parse((W/'fuse-trusted.py').read_text());shader=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='shader' for t in n.targets))
c=moderngl.create_standalone_context(require=430);dims=(64,64,32);shape=dims[::-1];origin=np.array([-.8,-.8,2.6]);voxel=.025;zero=np.zeros(np.prod(dims),'f4').tobytes();s=c.texture3d(dims,1,zero,dtype='f4');w=c.texture3d(dims,1,zero,dtype='f4');s.bind_to_image(0,read=True,write=True);w.bind_to_image(1,read=True,write=True);p=c.compute_shader(shader)
p['origin'].value=tuple(origin);p['dims'].value=dims;p['voxel'].value=voxel;p['mu'].value=.1;p['ranges'].value=2;p['depthSize'].value=(256,256);p['K'].value=(128,128,128,128)
y,x=np.mgrid[:256,:256];rays=np.stack([(x-128)/128,(y-128)/128,np.ones_like(x)],axis=-1);rays/=np.linalg.norm(rays,axis=-1,keepdims=True)
for angle,center in [(0,[0,0,0]),(.15,[.12,-.2,.1]),(-.1,[-.13,.1,-.1])]:
    ca,sa=np.cos(angle),np.sin(angle);R=np.array([[ca,0,sa],[0,1,0],[-sa,0,ca]]);center=np.asarray(center);direction=rays@R;ranges=(3-center[2])/direction[...,2];encoded=np.rint(ranges*1000).astype('u2');texture=c.texture((256,256),1,encoded.tobytes(),dtype='u2');texture.use(2);p['R'].write(np.asarray(R.T,'f4').tobytes());p['t'].value=tuple(-R@center);p.run(8,8,8);c.memory_barrier();texture.release()
c.finish();sums=np.frombuffer(s.read(),dtype='f4').reshape(shape);weights=np.frombuffer(w.read(),dtype='f4').reshape(shape);v=np.ones(shape,'f4');v[weights>0]=sums[weights>0]/weights[weights>0];roots=[]
for yy in range(4,60):
    for xx in range(4,60):
        a=v[:-1,yy,xx];b=v[1:,yy,xx];indices=np.flatnonzero((a>=0)&(b<0)&(weights[:-1,yy,xx]>=3)&(weights[1:,yy,xx]>=3))
        if len(indices)!=1:raise ValueError('Synthetic plane zero crossing missing or duplicated')
        i=int(indices[0]);fraction=a[i]/(a[i]-b[i]);roots.append(origin[2]+(i+.5+fraction)*voxel)
error=np.abs(np.asarray(roots)-3);before=s.read(),w.read();blank=c.texture((256,256),1,np.zeros((256,256),'u2').tobytes(),dtype='u2');blank.use(2);p.run(8,8,8);c.memory_barrier();c.finish();unchanged=before==(s.read(),w.read());assert error.max()<voxel*.5 and unchanged
report={'tests':'Known plane Z=3 reconstructed from three translated/rotated cameras using independently computed Euclidean ray ranges. Fully invalid depth must leave all weights and values unchanged.','cameraPoses':3,'maximumPlaneZError':float(error.max()),'meanPlaneZError':float(error.mean()),'voxelSceneUnits':voxel,'maskedDepthHasZeroInfluence':unchanged,'pass':True,'renderer':c.info['GL_RENDERER']}
(W/'tsdf-pilot/fusion-tests.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
