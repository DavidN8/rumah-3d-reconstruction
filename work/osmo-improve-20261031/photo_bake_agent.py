"""Photographic rebake of an uncompressed native mesh; original GLB is immutable.

Hidden OpenGL only. Registered OPENCV_FISHEYE photographs, eroded validity
masks, and a six-face first-hit mesh depth map determine a sharp best-view
texture. Native atlas is retained wherever photographs do not support a texel.
All coordinates are the normalized COLMAP/mesh world frame. UV/image row zero
is deliberately kept top-left in CPU arrays and GL texture storage alike.
"""
from __future__ import annotations
import argparse, hashlib, io, json, math, re, struct, sys, time
from pathlib import Path
import numpy as np
from PIL import Image
HERE=Path(__file__).resolve().parent
DEFAULT_HOLDOUT=','.join(f'cam0/frame_{i:06d}.jpg' for i in [3,25,41,61,81,111])
sys.path.insert(0,str(HERE/'pydeps'))
sys.path.insert(0,str(HERE.parent/'osmo-reconstruct-20261031'))
import moderngl
import cv2
from seed_fisheye import read_model, qvec_to_rotmat, Fisheye

UV_VERTEX='''#version 430
in vec3 in_pos; in vec3 in_norm; in vec2 in_uv;
out vec3 wp; out vec3 wn;
void main(){wp=in_pos;wn=in_norm;gl_Position=vec4(in_uv*2.0-1.0,0.0,1.0);}
'''
UV_FRAGMENT='''#version 430
in vec3 wp;in vec3 wn;
layout(location=0)out vec4 pos;layout(location=1)out vec4 norm;
void main(){pos=vec4(wp,1);norm=vec4(normalize(wn),1);}
'''
UV_CONSERVATIVE_VERTEX='''#version 430
in vec3 in_pos;in vec3 in_norm;in vec2 in_uv;
out vec3 vpos;out vec3 vnorm;out vec2 vuv;
void main(){vpos=in_pos;vnorm=in_norm;vuv=in_uv;gl_Position=vec4(0,0,0,1);}
'''
UV_CONSERVATIVE_GEOMETRY='''#version 430
layout(triangles)in;layout(triangle_strip,max_vertices=4)out;
in vec3 vpos[];in vec3 vnorm[];in vec2 vuv[];
flat out vec3 p0,p1,p2,n0,n1,n2;flat out vec2 u0,u1,u2;
uniform float uv_size,dilation_px;
void emit_corner(vec2 q){
 p0=vpos[0];p1=vpos[1];p2=vpos[2];n0=vnorm[0];n1=vnorm[1];n2=vnorm[2];
 u0=vuv[0]*uv_size;u1=vuv[1]*uv_size;u2=vuv[2]*uv_size;
 gl_Position=vec4(q/uv_size*2.0-1.0,0,1);EmitVertex();
}
void main(){
 vec2 lo=min(min(vuv[0],vuv[1]),vuv[2])*uv_size-vec2(dilation_px+.25);
 vec2 hi=max(max(vuv[0],vuv[1]),vuv[2])*uv_size+vec2(dilation_px+.25);
 emit_corner(lo);emit_corner(vec2(hi.x,lo.y));emit_corner(vec2(lo.x,hi.y));emit_corner(hi);EndPrimitive();
}
'''
UV_CONSERVATIVE_FRAGMENT='''#version 430
flat in vec3 p0,p1,p2,n0,n1,n2;flat in vec2 u0,u1,u2;
uniform float dilation_px;
layout(location=0)out vec4 pos;layout(location=1)out vec4 norm;
float cross2(vec2 a,vec2 b){return a.x*b.y-a.y*b.x;}
void main(){
 vec2 q=gl_FragCoord.xy;
 float area=cross2(u1-u0,u2-u0);float signum=area<0?-1.0:1.0;
 vec3 e=signum*vec3(cross2(u2-u1,q-u1),cross2(u0-u2,q-u2),cross2(u1-u0,q-u0));
 vec3 len=max(vec3(length(u2-u1),length(u0-u2),length(u1-u0)),vec3(1e-12));
 if(any(lessThan(e,-dilation_px*len)))discard;
 float s=e.x+e.y+e.z;vec3 bary;
 if(abs(s)<1e-20)bary=vec3(1.0/3.0);else{bary=max(e/s,vec3(0));bary/=bary.x+bary.y+bary.z;}
 pos=vec4(bary.x*p0+bary.y*p1+bary.z*p2,1);
 norm=vec4(normalize(bary.x*n0+bary.y*n1+bary.z*n2),1);
 vec2 nearest=bary.x*u0+bary.y*u1+bary.z*u2;
 // Interior samples take precedence over edge extension. Otherwise choose
 // the nearest clamped surface sample where neighboring triangles overlap.
 gl_FragDepth=all(greaterThanEqual(e,vec3(0)))?.01:.1+min(.8,length(q-nearest)*.2);
}
'''
DEPTH_VERTEX='''#version 430
in vec3 in_pos; uniform vec3 center,face_r,face_u,face_f;
uniform float proj_a,proj_b;out vec3 wp;
void main(){wp=in_pos;vec3 d=in_pos-center;float z=dot(d,face_f);
gl_Position=vec4(dot(d,face_r),dot(d,face_u),proj_a*z+proj_b,z);}
'''
DEPTH_FRAGMENT='''#version 430
in vec3 wp;uniform vec3 center;layout(location=0)out float radial;
void main(){radial=length(wp-center);}
'''
COMPUTE='''#version 430
layout(local_size_x=16,local_size_y=16)in;
layout(rgba32f,binding=0)uniform readonly image2D positions;
layout(rgba16f,binding=1)uniform readonly image2D normals;
layout(rgba32f,binding=2)uniform image2D best;
layout(r32f,binding=3)uniform image2D chosen;
layout(rgba32f,binding=4)uniform image2D color_sum;
layout(rgba32f,binding=5)uniform image2D color_square_sum;
layout(r32ui,binding=6)uniform uimage2D temporal_groups;
layout(r32ui,binding=7)uniform uimage2D consistent_groups;
uniform sampler2D photo,mask_img,depth_img,native_atlas;
uniform mat3 world_to_camera;uniform vec3 translation,center;
uniform vec4 focal_principal,distortion;
uniform vec2 photo_size;uniform int atlas_size,face_size,view_id;
uniform float visibility_absolute,visibility_relative,min_cosine,max_color_delta;
uniform int phase,time_bin,min_time_groups;
uniform float consensus_delta,max_color_std;
uniform float exposure_gain;
const vec3 FF[6]=vec3[6](vec3(1,0,0),vec3(-1,0,0),vec3(0,1,0),vec3(0,-1,0),vec3(0,0,1),vec3(0,0,-1));
const vec3 UU[6]=vec3[6](vec3(0,1,0),vec3(0,1,0),vec3(0,0,1),vec3(0,0,1),vec3(0,1,0),vec3(0,1,0));
void main(){
 ivec2 ij=ivec2(gl_GlobalInvocationID.xy);if(any(greaterThanEqual(ij,ivec2(atlas_size))))return;
 vec4 pw=imageLoad(positions,ij);if(pw.a<.5)return;
 vec3 d=pw.xyz-center;float range=length(d);if(range<.04)return;
 vec3 normal=normalize(imageLoad(normals,ij).xyz);float cosine=abs(dot(normal,d/range));
 if(cosine<min_cosine)return;
 vec3 pc=world_to_camera*pw.xyz+translation;float radial=length(pc.xy);
 float theta=atan(radial,pc.z);if(theta>1.8325957)return;
 float tt=theta*theta;float rr=theta*(1.0+tt*(distortion.x+tt*(distortion.y+tt*(distortion.z+tt*distortion.w))));
 vec2 pp=focal_principal.zw+focal_principal.xy*(radial>1e-8?pc.xy*(rr/radial):vec2(0));
 vec2 uv=pp/photo_size;if(any(lessThan(uv,vec2(0)))||any(greaterThanEqual(uv,vec2(1))))return;
 if(texture(mask_img,uv).r<.99)return;
 vec3 ad=abs(d);int face;
 if(ad.x>=ad.y&&ad.x>=ad.z)face=d.x>0?0:1;
 else if(ad.y>=ad.z)face=d.y>0?2:3;else face=d.z>0?4:5;
 vec3 f=FF[face],r=normalize(cross(f,UU[face])),u=cross(r,f);
 vec2 cuv=vec2(dot(d,r),dot(d,u))/dot(d,f)*.5+.5;
 cuv=clamp(cuv,vec2(.5/face_size),vec2(1.0-.5/face_size));
 vec2 duv=(vec2(face%3,face/3)+cuv)/vec2(3,2);
 float hit=texture(depth_img,duv).r;
 if(hit<=0.0||abs(hit-range)>visibility_absolute+visibility_relative*range)return;
 // Prefer frontal, close, optically central photographs. No averaging across
 // misregistered views: a high-resolution winner retains original photo detail.
 float lens=clamp((1.8325957-theta)/.42,0.05,1.0);
 vec3 rgb=texture(photo,uv).rgb;
 if(abs(exposure_gain-1.0)>1e-6){
  vec3 linear=mix(pow((rgb+.055)/1.055,vec3(2.4)),rgb/12.92,lessThanEqual(rgb,vec3(.04045)));
  linear=clamp(linear*exposure_gain,0.0,1.0);
  rgb=mix(1.055*pow(linear,vec3(1.0/2.4))-.055,12.92*linear,lessThanEqual(linear,vec3(.0031308)));
 }
 vec3 prior=texture(native_atlas,(vec2(ij)+.5)/float(atlas_size)).rgb;
 // Conservative optional foreground/color outlier rejection. A blurry native
 // atlas is only an approximate background prior, not photographic ground truth.
 if(length(rgb-prior)/sqrt(3.0)>max_color_delta)return;
 if(phase==0){
  float weight=max(.25,cosine)*max(.1,lens);
  vec4 sum=imageLoad(color_sum,ij),sq=imageLoad(color_square_sum,ij);
  imageStore(color_sum,ij,sum+vec4(rgb*weight,weight));
  imageStore(color_square_sum,ij,sq+vec4(rgb*rgb*weight,1));
  uint bits=imageLoad(temporal_groups,ij).r;
  imageStore(temporal_groups,ij,uvec4(bits|(1u<<uint(time_bin)),0,0,0));return;
 }
 if(phase==1){
  vec4 sum=imageLoad(color_sum,ij),sq=imageLoad(color_square_sum,ij);
  if(sum.w<=0.0||sq.w<3.0||bitCount(imageLoad(temporal_groups,ij).r)<min_time_groups)return;
  vec3 mean=sum.rgb/sum.w;vec3 variance=max(sq.rgb/sum.w-mean*mean,vec3(0));
  if(sqrt(dot(variance,vec3(1.0/3.0)))>max_color_std)return;
  if(length(rgb-mean)/sqrt(3.0)>consensus_delta)return;
  uint accepted_bits=imageLoad(consistent_groups,ij).r;
  imageStore(consistent_groups,ij,uvec4(accepted_bits|(1u<<uint(time_bin)),0,0,0));
 }
 float score=cosine*cosine*lens*lens/(.16+range*range);
 vec4 old=imageLoad(best,ij);if(score<=old.a)return;
 imageStore(best,ij,vec4(rgb,score));
 imageStore(chosen,ij,vec4(float(view_id),0,0,0));
}
'''

def load_glb(path):
    raw=Path(path).read_bytes()
    magic,version,size=struct.unpack_from('<III',raw)
    if (magic,version,size)!=(0x46546c67,2,len(raw)):raise ValueError('Invalid GLB')
    off=12;chunks={}
    while off<len(raw):
        n,k=struct.unpack_from('<II',raw,off);chunks[k]=raw[off+8:off+8+n];off+=8+n
    return raw,json.loads(chunks[0x4e4f534a]),chunks[0x004e4942]

def accessor(g,b,index):
    a=g['accessors'][index];v=g['bufferViews'][a['bufferView']]
    if a.get('sparse') or v.get('extensions'):raise ValueError('Need uncompressed native GLB')
    dt={5126:'<f4',5125:'<u4',5123:'<u2',5121:'u1',5122:'<i2',5120:'i1'}[a['componentType']]
    channels={'SCALAR':1,'VEC2':2,'VEC3':3,'VEC4':4}[a['type']]
    step=np.dtype(dt).itemsize*channels;stride=v.get('byteStride',step)
    arr=np.ndarray((a['count'],channels),dtype=dt,buffer=b,offset=v.get('byteOffset',0)+a.get('byteOffset',0),strides=(stride,np.dtype(dt).itemsize)).copy()
    if a.get('normalized') and a['componentType']!=5126:
        info=np.iinfo(np.dtype(dt));arr=arr.astype(np.float32)/info.max
        if info.min<0:arr=np.maximum(arr,-1)
    return arr

def mesh_data(g,b):
    if len(g['meshes'])!=1 or len(g['meshes'][0]['primitives'])!=1:raise ValueError('Single native primitive required')
    p=g['meshes'][0]['primitives'][0]
    if p.get('mode',4)!=4:raise ValueError('Triangles required')
    # Refuse transformed hierarchy rather than accidentally baking wrong poses.
    for n in g.get('nodes',[]):
        if 'mesh' in n and any(k in n for k in ['matrix','translation','rotation','scale']):
            mat=np.array(n.get('matrix',np.eye(4).T.reshape(-1))).reshape(4,4).T
            if not np.allclose(mat,np.eye(4)) or any(k in n for k in ['translation','rotation','scale']):raise ValueError('Mesh node transform must be identity; normalize explicitly first')
    xyz=accessor(g,b,p['attributes']['POSITION']).astype('f4')
    uv=accessor(g,b,p['attributes']['TEXCOORD_0']).astype('f4')
    ix=accessor(g,b,p['indices']).reshape(-1).astype('u4')
    if 'NORMAL' in p['attributes']:norm=accessor(g,b,p['attributes']['NORMAL']).astype('f4')
    else:
        norm=np.zeros_like(xyz);f=ix.reshape(-1,3);nn=np.cross(xyz[f[:,1]]-xyz[f[:,0]],xyz[f[:,2]]-xyz[f[:,0]])
        for c in range(3):np.add.at(norm,f[:,c],nn)
        norm/=np.maximum(np.linalg.norm(norm,axis=1,keepdims=True),1e-10)
    material=g['materials'][p.get('material',0)]
    tex_idx=material['pbrMetallicRoughness']['baseColorTexture']['index'];image_idx=g['textures'][tex_idx]['source']
    im=g['images'][image_idx];v=g['bufferViews'][im['bufferView']]
    atlas=Image.open(io.BytesIO(b[v.get('byteOffset',0):v.get('byteOffset',0)+v['byteLength']])).convert('RGB')
    return xyz,norm,uv,ix,image_idx,atlas

def write_glb(g,b,image_idx,jpeg,out):
    # Append while preserving original binary geometry exactly; packer later
    # removes the now-unreferenced original image bytes.
    b=b+b'\0'*((-len(b))%4);offset=len(b);b+=jpeg
    g['bufferViews'].append({'buffer':0,'byteOffset':offset,'byteLength':len(jpeg)})
    g['images'][image_idx]={'bufferView':len(g['bufferViews'])-1,'mimeType':'image/jpeg'}
    g['buffers'][0]['byteLength']=len(b)
    for m in g.get('materials',[]):m.setdefault('extensions',{})['KHR_materials_unlit']={}
    g['extensionsUsed']=list(dict.fromkeys(g.get('extensionsUsed',[])+['KHR_materials_unlit']))
    js=json.dumps(g,separators=(',',':')).encode();js+=b' '*((-len(js))%4);b+=b'\0'*((-len(b))%4)
    result=struct.pack('<III',0x46546c67,2,12+8+len(js)+8+len(b))+struct.pack('<II',len(js),0x4e4f534a)+js+struct.pack('<II',len(b),0x004e4942)+b
    Path(out).write_bytes(result)

class Baker:
    def __init__(self,xyz,norm,uv,indices,size,face_size,native=None,uv_dilation=.75):
        self.ctx=c=moderngl.create_standalone_context(require=430);self.size=size;self.face_size=face_size
        self.vbo=c.buffer(np.column_stack([xyz,norm,uv]).astype('f4').tobytes());self.ibo=c.buffer(indices.astype('u4').tobytes())
        self.uv_prog=(c.program(vertex_shader=UV_CONSERVATIVE_VERTEX,geometry_shader=UV_CONSERVATIVE_GEOMETRY,fragment_shader=UV_CONSERVATIVE_FRAGMENT)
                      if uv_dilation else c.program(vertex_shader=UV_VERTEX,fragment_shader=UV_FRAGMENT))
        if uv_dilation:self.uv_prog['uv_size'].value=float(size);self.uv_prog['dilation_px'].value=uv_dilation
        self.uv_vao=c.vertex_array(self.uv_prog,[(self.vbo,'3f 3f 2f','in_pos','in_norm','in_uv')],self.ibo,index_element_size=4)
        self.depth_prog=c.program(vertex_shader=DEPTH_VERTEX,fragment_shader=DEPTH_FRAGMENT)
        self.depth_vao=c.vertex_array(self.depth_prog,[(self.vbo,'3f 20x','in_pos')],self.ibo,index_element_size=4)
        self.pos=c.texture((size,size),4,dtype='f4');self.norm=c.texture((size,size),4,dtype='f2')
        self.uv_fbo=c.framebuffer([self.pos,self.norm],c.depth_renderbuffer((size,size)));self.uv_fbo.use();self.uv_fbo.clear(depth=1);c.viewport=(0,0,size,size)
        c.enable(moderngl.DEPTH_TEST);c.disable(moderngl.CULL_FACE|moderngl.BLEND);self.uv_vao.render();c.disable(moderngl.DEPTH_TEST)
        self.best=c.texture((size,size),4,dtype='f4');self.best.write(bytes(size*size*16))
        self.choice=c.texture((size,size),1,dtype='f4');self.choice.write(bytes(size*size*4))
        self.sum=c.texture((size,size),4,dtype='f4');self.sum.write(bytes(size*size*16))
        self.square=c.texture((size,size),4,dtype='f4');self.square.write(bytes(size*size*16))
        self.time_bits=c.texture((size,size),1,dtype='u4');self.time_bits.write(bytes(size*size*4))
        self.consistent_bits=c.texture((size,size),1,dtype='u4');self.consistent_bits.write(bytes(size*size*4))
        self.depth=c.texture((3*face_size,2*face_size),1,dtype='f4');self.depth.filter=(moderngl.NEAREST,moderngl.NEAREST)
        self.depth.repeat_x=self.depth.repeat_y=False
        self.depth_fbo=c.framebuffer([self.depth],c.depth_renderbuffer((3*face_size,2*face_size)))
        self.compute=c.compute_shader(COMPUTE)
        for tex,unit in [(self.pos,0),(self.norm,1),(self.best,2),(self.choice,3)]:tex.bind_to_image(unit,read=True,write=unit>=2)
        for tex,unit in [(self.sum,4),(self.square,5),(self.time_bits,6),(self.consistent_bits,7)]:tex.bind_to_image(unit,read=True,write=True)
        self.compute['photo'].value=4;self.compute['mask_img'].value=5;self.compute['depth_img'].value=6
        self.compute['native_atlas'].value=7
        if native is None:native=Image.new('RGB',(1,1),(128,128,128))
        self.native=c.texture(native.size,3,np.asarray(native).tobytes(),alignment=1);self.native.filter=(moderngl.LINEAR,moderngl.LINEAR);self.native.repeat_x=self.native.repeat_y=False;self.native.use(7)
        self.compute['atlas_size'].value=size;self.compute['face_size'].value=face_size
        self.depth.use(6);self.last_center=None

    def depth_pass(self,center):
        if self.last_center is not None and np.linalg.norm(center-self.last_center)<1e-5:return
        c=self.ctx;p=self.depth_prog;s=self.face_size;self.depth_fbo.use();self.depth_fbo.clear(0,0,0,0,depth=1)
        c.enable(moderngl.DEPTH_TEST);c.disable(moderngl.CULL_FACE|moderngl.BLEND)
        p['center'].value=tuple(center);near,far=.015,100.
        p['proj_a'].value=(far+near)/(far-near);p['proj_b'].value=-2*far*near/(far-near)
        forwards=np.array([[1,0,0],[-1,0,0],[0,1,0],[0,-1,0],[0,0,1],[0,0,-1]],float)
        for face,f in enumerate(forwards):
            up=np.array([0,0,1] if face in [2,3] else [0,1,0]);right=np.cross(f,up);up=np.cross(right,f)
            p['face_f'].value=tuple(f);p['face_r'].value=tuple(right);p['face_u'].value=tuple(up)
            c.viewport=((face%3)*s,(face//3)*s,s,s);self.depth_vao.render()
        c.disable(moderngl.DEPTH_TEST);self.last_center=center.copy()

    def add_view(self,r,t,params,rgb,mask,view_id,abs_tol=.02,rel_tol=.004,min_cos=.25,max_color_delta=2,phase=2,time_bin=0,min_time_groups=3,consensus_delta=.16,max_color_std=.20,exposure_gain=1):
        c=self.ctx;center=-r.T@t;self.depth_pass(center)
        h,w=rgb.shape[:2];photo=c.texture((w,h),3,rgb.tobytes(),alignment=1);photo.filter=(moderngl.LINEAR,moderngl.LINEAR)
        photo.repeat_x=photo.repeat_y=False;photo.use(4)
        m=c.texture((w,h),1,mask.tobytes(),alignment=1);m.filter=(moderngl.NEAREST,moderngl.NEAREST);m.repeat_x=m.repeat_y=False;m.use(5)
        p=self.compute;p['world_to_camera'].write(np.asarray(r.T,dtype='f4').tobytes());p['translation'].value=tuple(t);p['center'].value=tuple(center)
        p['focal_principal'].value=tuple(params[:4]);p['distortion'].value=tuple(params[4:]);p['photo_size'].value=(w,h)
        p['view_id'].value=view_id;p['visibility_absolute'].value=abs_tol;p['visibility_relative'].value=rel_tol;p['min_cosine'].value=min_cos
        p['max_color_delta'].value=max_color_delta
        p['phase'].value=phase;p['time_bin'].value=time_bin;p['min_time_groups'].value=min_time_groups;p['consensus_delta'].value=consensus_delta;p['max_color_std'].value=max_color_std
        p['exposure_gain'].value=exposure_gain
        p.run((self.size+15)//16,(self.size+15)//16,1);c.memory_barrier();photo.release();m.release()

    def result(self):
        s=self.size
        return (np.frombuffer(self.pos.read(),dtype='f4').reshape(s,s,4),
                np.frombuffer(self.best.read(),dtype='f4').reshape(s,s,4),
                np.frombuffer(self.choice.read(),dtype='f4').reshape(s,s).astype(np.int32))

def find_mask(root,name):
    p=Path(name)
    for q in [root/p.with_suffix('.png'),root/Path(str(p)+'.png'),root/p]:
        if q.exists():return q
    raise FileNotFoundError(f'Missing mask for {name}; refusing unmasked operator/source')

def self_test():
    # Fronto-parallel plane with an independently projected RGB coordinate ramp.
    xyz=np.array([[-1,-1,3],[1,-1,3],[1,1,3],[-1,1,3]],'f4');norm=np.tile([0,0,-1],(4,1)).astype('f4')
    uv=np.array([[0,0],[1,0],[1,1],[0,1]],'f4');ix=np.array([0,1,2,0,2,3],'u4')
    b=Baker(xyz,norm,uv,ix,96,128);yy,xx=np.mgrid[:256,:256]
    rgb=np.stack([xx,yy,np.full_like(xx,83)],-1).astype('u1');mask=np.full((256,256),255,'u1')
    params=np.array([97,104,133,119,.01,-.002,.0004,-.00003],float);camera={'model':'OPENCV_FISHEYE','width':256,'height':256,'params':params}
    tests=[]
    for angle in [0,.7,-1.1]:
        ca,sa=math.cos(angle),math.sin(angle);r=np.array([[ca,-sa,0],[sa,ca,0],[0,0,1]])
        b.add_view(r,np.zeros(3),params,rgb,mask,len(tests)+1,abs_tol=.025)
        pos,best,_=b.result();valid=best[...,3]>0;xy=Fisheye(camera).project((pos[...,:3]@r.T).reshape(-1,3))[0].reshape(96,96,2)
        # Pixel-center convention: GL bilinear pixel x samples source index x-.5.
        expect=np.clip(np.dstack([xy[...,0]-.5,xy[...,1]-.5,np.full((96,96),83)]),0,255)
        # Reset winner so each rolled pose independently wins all its visible texels.
        err=np.abs(best[...,:3]*255-expect)[valid];tests.append({'roll_rad':angle,'coverage':float(valid.mean()),'interior_coverage':float(valid[4:-4,4:-4].mean()),'max_channel_error':float(err.max()),'mean_channel_error':float(err.mean())})
        b.best.write(bytes(96*96*16));b.choice.write(bytes(96*96*4))
    # Add an occluder square between camera and textured plane. Occluded target
    # atlas center must not acquire photograph data (fallback is intentional).
    xyz2=np.concatenate([xyz,np.array([[-.35,-.35,1.5],[.35,-.35,1.5],[.35,.35,1.5],[-.35,.35,1.5]],'f4')])
    uv2=np.concatenate([uv,np.full((4,2),-.2,'f4')]);ix2=np.concatenate([ix,ix+4]);n2=np.tile([0,0,-1],(8,1)).astype('f4')
    oc=Baker(xyz2,n2,uv2,ix2,96,128);oc.add_view(np.eye(3),np.zeros(3),params,rgb,mask,1)
    _,oc_best,_=oc.result();blocked=int(np.count_nonzero(oc_best[32:64,32:64,3]));outer=int(np.count_nonzero(oc_best[:12,:,3]))
    # Lens-edge rays have camera z<0: a pinhole visibility shortcut would reject
    # the entire plane. Also tests a nonzero camera center and anisotropic focal.
    center=np.array([.13,-.17,.09]);small=xyz.copy();small[:,:2]*=.15;small+=center
    beyond=Baker(small,norm,uv,ix,64,128);angle=math.radians(100);ca,sa=math.cos(angle),math.sin(angle)
    r=np.array([[ca,0,sa],[0,1,0],[-sa,0,ca]]);t=-r@center
    ep=np.array([55,59,127,123,.01,-.002,.0004,-.00003],float)
    beyond.add_view(r,t,ep,rgb,mask,1);pp,eb,_=beyond.result();valid=eb[...,3]>0
    ec={'model':'OPENCV_FISHEYE','width':256,'height':256,'params':ep};xy=Fisheye(ec).project((pp[...,:3]@r.T+t).reshape(-1,3))[0].reshape(64,64,2)
    expect=np.clip(np.dstack([xy[...,0]-.5,xy[...,1]-.5,np.full((64,64),83)]),0,255)
    edge={'theta_center_degrees':100,'translated_center':center.tolist(),'interior_coverage':float(valid[5:-5,5:-5].mean()),'max_channel_error':float(np.abs(eb[...,:3]*255-expect)[valid].max())}
    cons=Baker(xyz,norm,uv,ix,64,128);white=np.full_like(rgb,190);blue=np.empty_like(rgb);blue[:]=[60,100,220]
    for phase in [0,1]:
        for j,photo in enumerate([blue,white,white,white],1):cons.add_view(np.eye(3),np.zeros(3),params,photo,mask,j,phase=phase,time_bin=j-1)
    _,cb,cc=cons.result();cv=cb[5:-5,5:-5,3]>0;winner_blue=int((cc[5:-5,5:-5][cv]==1).sum())
    accepted_time_bits=np.frombuffer(cons.consistent_bits.read(),dtype='u4').reshape(64,64)
    consensus_test={'interior_coverage':float(cv.mean()),'blue_outlier_winning_texels':winner_blue,'max_gray_error_255':float(np.max(np.abs(cb[5:-5,5:-5,:3][cv]*255-190))),'color_agreeing_time_groups_at_center':int(accepted_time_bits[32,32]).bit_count()}
    # A tiny UV island falls between all texel centers. Native matching0.75px
    # edge coverage must preserve it; strict GL triangle rasterization misses it.
    tiny_uv=np.array([[48.1,48.1],[48.3,48.1],[48.1,48.3]],'f4')/96
    tiny_xyz=xyz[:3];tiny_norm=norm[:3];tiny_ix=np.arange(3,dtype='u4')
    exact=Baker(tiny_xyz,tiny_norm,tiny_uv,tiny_ix,96,32,uv_dilation=0);exact_pos,_,_=exact.result()
    dilated=Baker(tiny_xyz,tiny_norm,tiny_uv,tiny_ix,96,32,uv_dilation=.75);dilated_pos,_,_=dilated.result()
    tiny_test={'exact_center_occupied_texels':int(np.count_nonzero(exact_pos[...,3])),'native_matching_occupied_texels':int(np.count_nonzero(dilated_pos[...,3])),'plane_z_max_error':float(np.max(np.abs(dilated_pos[dilated_pos[...,3]>0,2]-3)))}
    exposure=Baker(xyz,norm,uv,ix,32,64);flat=np.empty_like(rgb);flat[:]=[70,130,190]
    exposure.add_view(np.eye(3),np.zeros(3),params,flat,mask,1,exposure_gain=2**.2)
    _,epix,_=exposure.result();col=np.array([70,130,190],float)/255;linear=np.where(col<=.04045,col/12.92,((col+.055)/1.055)**2.4)*2**.2
    expected=np.where(linear<=.0031308,linear*12.92,1.055*linear**(1/2.4)-.055)
    gain_error=float(np.max(np.abs(epix[epix[...,3]>0,:3]-expected))*255)
    report={'renderer':b.ctx.info['GL_RENDERER'],'plane_tests':tests,'beyond_90_degrees_test':edge,'occluded_center_supported_pixels':blocked,'visible_outer_supported_pixels':outer,'temporal_color_consensus_test':consensus_test,'subpixel_uv_island_test':tiny_test,'scalar_linear_exposure_max_error_255':gain_error}
    if any(t['interior_coverage']<.999 or t['max_channel_error']>1.1 for t in tests) or blocked or outer==0 or edge['interior_coverage']<.99 or edge['max_channel_error']>1.1 or winner_blue or consensus_test['interior_coverage']<.99 or consensus_test['max_gray_error_255']>.1 or consensus_test['color_agreeing_time_groups_at_center']!=3 or tiny_test['exact_center_occupied_texels']!=0 or tiny_test['native_matching_occupied_texels']<1 or tiny_test['plane_z_max_error']>1e-5 or gain_error>.01:raise AssertionError(report)
    (HERE/'photo-bake-selftest.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2));return report

def main():
    p=argparse.ArgumentParser();p.add_argument('--self-test',action='store_true');p.add_argument('--mesh',type=Path);p.add_argument('--dataset',type=Path)
    p.add_argument('--images-root',type=Path);p.add_argument('--masks-root',type=Path);p.add_argument('--output',type=Path)
    p.add_argument('--texture-size',type=int,default=4096);p.add_argument('--face-size',type=int,default=1024)
    p.add_argument('--stride',type=int,default=1);p.add_argument('--limit',type=int,default=0);p.add_argument('--gutter',type=int,default=8)
    p.add_argument('--exclude-images',default=DEFAULT_HOLDOUT,help='Comma-separated registered names excluded from texture selection. Default six website comparison photos; geometry training still used these images.')
    p.add_argument('--visibility-absolute',type=float,default=.02);p.add_argument('--visibility-relative',type=float,default=.004)
    p.add_argument('--min-cosine',type=float,default=.25);p.add_argument('--mask-erosion',type=int,default=8)
    p.add_argument('--uv-dilation',type=float,default=.75,help='Conservative UV edge coverage in pixels; matches native bake0.75.0 reproduces exact-center diagnostic.')
    p.add_argument('--max-color-delta',type=float,default=2,help='Optional RMS RGB disagreement gate against blurry native atlas, in0..1. Default2 disables; e.g0.28 rejects severe foreground/color mismatches.')
    p.add_argument('--single-pass',action='store_true',help='Disable consensus, for diagnostic comparisons only.')
    p.add_argument('--consensus-delta',type=float,default=.16);p.add_argument('--max-color-std',type=float,default=.20)
    p.add_argument('--min-time-groups',type=int,default=3);p.add_argument('--time-group-seconds',type=float,default=3)
    p.add_argument('--exposure-gains',type=Path,help='Optional calibrated scalar linear exposure gains JSON. Clamp<=0.2stops enforced. Default no correction.')
    args=p.parse_args()
    if args.self_test:self_test();return
    if not all([args.mesh,args.dataset,args.output]):p.error('--mesh --dataset --output required')
    if args.output.exists():raise FileExistsError('Output exists; choose fresh output to preserve previous result')
    exposure_metadata=json.loads(args.exposure_gains.read_text()) if args.exposure_gains else None
    exposure_stops=exposure_metadata['correction_stops_by_image'] if exposure_metadata else {}
    if any(not np.isfinite(x) or abs(x)>.200001 for x in exposure_stops.values()):raise ValueError('Scalar exposure gains must be finite and clamped to±0.2stops')
    start=time.monotonic();raw,g,b=load_glb(args.mesh);source_hash=hashlib.sha256(raw).hexdigest();xyz,norm,uv,ix,image_idx,native=mesh_data(g,b)
    print(f'Mesh {len(ix)//3:,} faces; {len(xyz):,} UV vertices; creating {args.texture_size} atlas',flush=True)
    baker=Baker(xyz,norm,uv,ix,args.texture_size,args.face_size,native,args.uv_dilation)
    cameras,images,_=read_model(args.dataset/'sparse'/'0');root=args.images_root or args.dataset/'images';mroot=args.masks_root or args.dataset/'masks'
    # Interleave lenses by timestamp to expose progress fairly across room sides.
    excluded={name.strip().replace('\\','/') for name in args.exclude_images.split(',') if name.strip()}
    absent=excluded-{im['name'].replace('\\','/') for im in images.values()}
    if absent:raise ValueError(f'Excluded image not registered; check names: {sorted(absent)}')
    if exposure_metadata and not excluded.issubset(set(exposure_metadata.get('excluded_from_fit',[]))):raise ValueError('Texture comparison holdouts must also be excluded from exposure gain fitting')
    views=sorted([im for im in images.values() if im['name'].replace('\\','/') not in excluded],key=lambda im:(Path(im['name']).stem,im['name']))[::args.stride]
    if args.limit:views=views[:args.limit]
    sources=[]
    for phase in ([2] if args.single_pass else [0,1]):
      for j,im in enumerate(views,1):
        rgb=np.asarray(Image.open(root/im['name']).convert('RGB'));h,w=rgb.shape[:2]
        mask=np.asarray(Image.open(find_mask(mroot,im['name'])).convert('L'))
        if mask.shape!=(h,w):raise ValueError('Mask/image shape mismatch')
        if args.mask_erosion:mask=cv2.erode(mask,np.ones((2*args.mask_erosion+1,)*2,'u1'))
        camera=cameras[im['camera_id']];fish=Fisheye(camera,width=w,height=h)
        params=np.r_[fish.fx,fish.fy,fish.cx,fish.cy,fish.k]
        frame=int(re.search(r'(\d+)$',Path(im['name']).stem).group(1));time_bin=int(((frame-1)/2)/args.time_group_seconds)
        if time_bin>=32:raise ValueError('More than32 temporal groups; increase --time-group-seconds')
        correction_stops=float(exposure_stops.get(im['name'],0))
        r=qvec_to_rotmat(im['qvec']);t=im['tvec'];baker.add_view(r,t,params,rgb,mask,j,args.visibility_absolute,args.visibility_relative,args.min_cosine,args.max_color_delta,phase,time_bin,args.min_time_groups,args.consensus_delta,args.max_color_std,2**correction_stops)
        if phase in [1,2]:sources.append({'view_id':j,'name':im['name'],'width':w,'height':h,'camera_id':im['camera_id'],'time_bin':time_bin,'scalar_exposure_correction_stops':correction_stops})
        if j%8==0 or j==len(views):print(json.dumps({'phase':phase,'views':j,'total':len(views),'seconds':round(time.monotonic()-start,1)}),flush=True)
    pos,best,choice=baker.result();occupied=pos[...,3]>.5;supported=occupied&(best[...,3]>0);s=args.texture_size
    if not args.single_pass:
        matching_bits=np.frombuffer(baker.consistent_bits.read(),dtype='u4').reshape(s,s);matching_groups=np.zeros((s,s),'u1')
        for shift in range(32):matching_groups+=((matching_bits>>shift)&1).astype('u1')
        supported&=matching_groups>=args.min_time_groups
    output=np.array(native.resize((s,s),Image.Resampling.LANCZOS));output[supported]=np.clip(best[supported,:3]*255+.5,0,255).astype('u1')
    # Extend only chart gutters. Unsupported real surface texels retain native.
    if args.gutter:
        outside=(~occupied).astype('u1');distance,labels=cv2.distanceTransformWithLabels(outside,cv2.DIST_L2,5,labelType=cv2.DIST_LABEL_PIXEL)
        lut=np.zeros((int(labels.max())+1,3),'u1');lut[labels[occupied]]=output[occupied]
        gutter=(~occupied)&(distance<=args.gutter);output[gutter]=lut[labels[gutter]]
    # Quantify color jumps at best-view seams, separating them from within-view
    # neighboring differences; natural texture edges are included in both.
    seam_jumps=[];within_jumps=[]
    for axis in [0,1]:
        a=[slice(None),slice(None)];z=a.copy();a[axis]=slice(None,-1);z[axis]=slice(1,None);a,z=tuple(a),tuple(z)
        # Exclude unrelated UV islands sitting next to each other in the atlas.
        # This is a local diagnostic, not a full welded-edge seam measurement.
        spatial_neighbors=np.linalg.norm(pos[a][:,:,:3]-pos[z][:,:,:3],axis=-1)<=.03
        both=supported[a]&supported[z]&spatial_neighbors;changed=choice[a]!=choice[z];diff=np.mean(np.abs(output[a].astype('f4')-output[z].astype('f4')),axis=-1)
        seam_jumps.append(diff[both&changed]);within_jumps.append(diff[both&~changed])
    stats=lambda rows:{'pairs':int(sum(len(x) for x in rows)),'mean_rgb_jump_255':float(np.mean(np.concatenate(rows))) if sum(len(x) for x in rows) else None,'p95_rgb_jump_255':float(np.percentile(np.concatenate(rows),95)) if sum(len(x) for x in rows) else None}
    encoded=io.BytesIO();Image.fromarray(output).save(encoded,format='JPEG',quality=94,subsampling=0,optimize=True)
    args.output.parent.mkdir(parents=True,exist_ok=True);write_glb(g,b,image_idx,encoded.getvalue(),args.output)
    Image.fromarray(output).resize((1536,1536)).save(args.output.with_suffix('.atlas-preview.jpg'),quality=90)
    Image.fromarray((supported.astype('u1')*255)).resize((1024,1024)).save(args.output.with_suffix('.photo-support.png'))
    winners=np.bincount(choice[supported],minlength=len(sources)+1)
    for source in sources:source['winning_texels']=int(winners[source['view_id']])
    report={'mesh':str(args.mesh),'output':str(args.output),'source_sha256':source_hash,'original_unchanged':hashlib.sha256(args.mesh.read_bytes()).hexdigest()==source_hash,
        'renderer':baker.ctx.info['GL_RENDERER'],'faces':len(ix)//3,'uv_vertices':len(xyz),'texture_size':s,'depth_face_size':args.face_size,
        'uv_edge_dilation_pixels':args.uv_dilation,'uv_coverage_scope':'Conservatively rasterized chart samples including edge band; original triangles/UVs unchanged.',
        'occupied_texels':int(occupied.sum()),'photographically_supported_texels':int(supported.sum()),'supported_fraction_of_occupied':float(supported.sum()/max(1,occupied.sum())),
        'fallback_texels':int((occupied&~supported).sum()),'native_fallback':'Gaussian DC original atlas retained where no unmasked first-hit photograph supports surface',
        'selection':'highest cosine²*lens_confidence²/(0.16+distance²), one photographic winner per texel; two-pass color/temporal consensus unless diagnostic single-pass requested',
        'consensus_enabled':not args.single_pass,'consensus_rgb_rms_delta_0_1':args.consensus_delta,'max_rgb_rms_std_0_1':args.max_color_std,'min_time_groups':args.min_time_groups,'time_group_seconds':args.time_group_seconds,
        'temporal_support_scope':'At least min_time_groups distinct3-second bins with photos individually matching consensus color; geometry/poses still in-sample.',
        'excluded_texture_views':sorted(excluded),'validation_scope':'Excluded source photos are held out from texturing only. Geometry/poses were trained using them; this is not a held-out reconstruction test.',
        'exposure_gains_file':str(args.exposure_gains) if args.exposure_gains else None,'exposure_gain_fit_basis':exposure_metadata['fit_basis'] if exposure_metadata else None,'exposure_gain_fit_excludes_texture_holdouts':bool(exposure_metadata) and excluded.issubset(set(exposure_metadata.get('excluded_from_fit',[]))),
        'visibility_absolute':args.visibility_absolute,'visibility_relative':args.visibility_relative,'min_cosine':args.min_cosine,'mask_erosion_pixels':args.mask_erosion,
        'native_color_prior_max_rms_delta_0_1':args.max_color_delta,
        'view_seams':stats(seam_jumps),'within_view_neighbors':stats(within_jumps),'seam_metric_scope':'Neighboring supported atlas texels with world-position separation<=0.03 approximate meters; not a complete welded UV-chart seam analysis.',
        'jpeg_bytes':len(encoded.getvalue()),'glb_bytes':args.output.stat().st_size,
        'source_views':sources,'seconds':time.monotonic()-start,'coordinate_frame':'unchanged normalized COLMAP/mesh frame; four-term calibrated OPENCV_FISHEYE; image top-left storage',
        'limitations':['Photography cannot repair geometric surface errors.','Masked/occluded/unseen surfaces keep original native texture; supported coverage is not geometric validation.','Best-view seams can remain because source exposure or reconstructed surfaces differ.']}
    if not report['original_unchanged']:raise AssertionError('Original source unexpectedly changed')
    args.output.with_suffix('.photo-bake-report.json').write_text(json.dumps(report,indent=2))
    print(json.dumps({k:v for k,v in report.items() if k!='source_views'},indent=2),flush=True)

if __name__=='__main__':main()
