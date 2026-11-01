"""Independent hidden-OpenGL, unlit six-reference appearance comparison."""
import argparse,json,time
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw
import photo_bake_agent as pb

VERT='''#version 430
in vec3 in_pos;in vec2 in_uv;out vec2 uv;
uniform vec3 center,rr,uu,ff;uniform float aa,bb;
void main(){vec3 d=in_pos-center;float z=dot(d,ff);gl_Position=vec4(dot(d,rr),dot(d,uu),aa*z+bb,z);uv=in_uv;}
'''
FRAG='''#version 430
in vec2 uv;uniform sampler2D atlas;out vec4 color;
void main(){color=vec4(texture(atlas,uv).rgb,1);}
'''
def main():
    p=argparse.ArgumentParser();p.add_argument('--meshes',type=Path,nargs='+',required=True);p.add_argument('--cameras',type=Path,default=Path(__file__).parent.parent/'mobile-20261029/legacy-osmo-cameras-v1.json');p.add_argument('--output',type=Path,required=True);p.add_argument('--size',type=int,default=600);a=p.parse_args()
    start=time.monotonic();presets=json.loads(a.cameras.read_text())['presets'];ctx=pb.moderngl.create_standalone_context(require=430);s=a.size
    fbo=ctx.framebuffer([ctx.texture((s,s),4)],ctx.depth_renderbuffer((s,s)));prog=ctx.program(vertex_shader=VERT,fragment_shader=FRAG)
    prog['atlas'].value=0;prog['aa'].value=(100+.02)/(100-.02);prog['bb'].value=-2*100*.02/(100-.02)
    fbo.use();ctx.viewport=(0,0,s,s);ctx.enable(pb.moderngl.DEPTH_TEST);ctx.disable(pb.moderngl.CULL_FACE|pb.moderngl.BLEND)
    rows=[];metrics=[]
    for mesh in a.meshes:
        raw,g,b=pb.load_glb(mesh);xyz,norm,uv,ix,_,atlas=pb.mesh_data(g,b)
        vbo=ctx.buffer(np.column_stack([xyz,uv]).astype('f4').tobytes());ibo=ctx.buffer(ix.tobytes());vao=ctx.vertex_array(prog,[(vbo,'3f 2f','in_pos','in_uv')],ibo,index_element_size=4)
        tex=ctx.texture(atlas.size,3,np.asarray(atlas).tobytes(),alignment=1);tex.filter=(pb.moderngl.LINEAR,pb.moderngl.LINEAR);tex.repeat_x=tex.repeat_y=False;tex.use(0)
        renders=[];mm=[]
        for pre in presets:
            q=pre['quaternion'];rot=pb.qvec_to_rotmat([q[3],*q[:3]])
            for name,val in [('rr',rot[:,0]),('uu',rot[:,1]),('ff',-rot[:,2]),('center',pre['position'])]:prog[name].value=tuple(val)
            fbo.clear(0,0,0,0,depth=1);vao.render()
            render=np.flipud(np.frombuffer(fbo.read(components=4,alignment=1),dtype='u1').reshape(s,s,4)).copy()
            ref=Image.open(pre['sourceFile']).convert('RGB').resize((s,s),Image.Resampling.LANCZOS);src=np.asarray(ref)
            mask_path=Path(pre['sourceFile']).with_name(Path(pre['sourceFile']).stem+'-valid.png');mask=np.asarray(Image.open(mask_path).convert('L').resize((s,s),Image.Resampling.NEAREST))>127
            covered=(render[...,3]>127)&mask;err=render[covered,:3].astype(float)-src[covered].astype(float)
            rmse=float(np.sqrt(np.mean(err*err)));mae=float(np.mean(np.abs(err)))
            mm.append({'view':pre['name'],'covered_fraction':float(covered.sum()/max(1,mask.sum())),'covered_rgb_rmse_255':rmse,'covered_rgb_mae_255':mae})
            renders.append(Image.fromarray(render[...,:3]));
        rows.append((mesh.stem,renders));metrics.append({'mesh':str(mesh),'views':mm,'mean_rmse_255':float(np.mean([m['covered_rgb_rmse_255'] for m in mm]))})
        tex.release();vao.release();vbo.release();ibo.release()
    refs=[Image.open(pre['sourceFile']).convert('RGB').resize((s,s),Image.Resampling.LANCZOS) for pre in presets];rows.insert(0,('texture-only holdout photographs',refs))
    sheet=Image.new('RGB',(s*len(presets),len(rows)*(s+32)),(28,31,35));draw=ImageDraw.Draw(sheet)
    for j,(name,ims) in enumerate(rows):
        draw.text((8,j*(s+32)+8),name,fill='white')
        for k,im in enumerate(ims):sheet.paste(im,(k*s,j*(s+32)+32))
    a.output.parent.mkdir(parents=True,exist_ok=True);sheet.save(a.output.with_suffix('.jpg'),quality=94,subsampling=0)
    report={'renderer':ctx.info['GL_RENDERER'],'pixel_size':s,'seconds':time.monotonic()-start,'scope':'Unlit geometry and texture. Six source photos excluded from photographic texture selection, but used for geometry/poses. Covered-pixel errors do not validate missing geometry.','models':metrics}
    a.output.with_suffix('.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
if __name__=='__main__':main()
