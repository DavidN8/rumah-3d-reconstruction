"""Bounded local planar UV patches: no large conformal solve or geometry edit."""
from pathlib import Path
import sys,json,time,io,struct,shutil
import numpy as np
from PIL import Image
W=Path(__file__).resolve().parent;sys.path.insert(0,str(W.parent/'tsdfdeps'));import xatlas
OUT=W/'poisson-projected';OUT.mkdir(exist_ok=True)
if (OUT/'surface-uncompressed.glb').exists():raise FileExistsError('Preserve projected UV pilot')
started=time.monotonic();d=np.load(W/'poisson-pilot/surface-compact.npz');v=d['positions'];n=d['normals'];f=d['faces'];normal=np.cross(v[f[:,1]]-v[f[:,0]],v[f[:,2]]-v[f[:,0]]);area=np.linalg.norm(normal,axis=1);f=f[area>1e-12];normal=normal[area>1e-12];center=v[f].mean(axis=1);axis=np.argmax(np.abs(normal),axis=1);sign=normal[np.arange(len(normal)),axis]<0;bucket=axis+sign*3
# Spatial splitting bounds the curvature of each local projection. Seams only;
# all retained surface positions, normals and triangle connectivity are exact.
cell=np.floor(center/.5).astype('i4');groups=np.column_stack([bucket,cell]);unique,gid=np.unique(groups,axis=0,return_inverse=True);keys=gid.repeat(3).astype('i8')*len(v)+f.reshape(-1);key,idx=np.unique(keys,return_inverse=True);original_vertex=(key%len(v)).astype('u4');group=(key//len(v)).astype('i4');axis_per_vertex=unique[group,0]%3;uv=np.empty((len(key),2),'f4')
for a,axes in enumerate([(2,1),(0,2),(0,1)]):
    use=axis_per_vertex==a;uv[use]=v[original_vertex[use]][:,axes]
atlas=xatlas.Atlas();atlas.add_uv_mesh(uv,idx.reshape(-1,3).astype('u4'),face_materials=gid.astype('u4').reshape(-1,1));options=xatlas.PackOptions();options.resolution=8192;options.padding=4;options.blockAlign=True
print('Packing local projected patches',len(unique),'groups',len(f),'faces',flush=True);atlas.generate(pack_options=options,verbose=True);mapping,faces,uv=atlas[0];xyz=v[original_vertex[mapping]].astype('<f4');normal=n[original_vertex[mapping]].astype('<f4');uv=uv.astype('<f4');indices=faces.astype('<u4').reshape(-1)
buffers=[];views=[];accessors=[];offset=0
def add(payload,target=None):
    global offset
    payload+=b'\0'*((-len(payload))%4);row={'buffer':0,'byteOffset':offset,'byteLength':len(payload)}
    if target:row['target']=target
    views.append(row);buffers.append(payload);offset+=len(payload);return len(views)-1
for a,typ in [(xyz,'VEC3'),(normal,'VEC3'),(uv,'VEC2'),(indices,'SCALAR')]:
    view=add(a.tobytes(),34963 if typ=='SCALAR' else 34962);acc={'bufferView':view,'componentType':5125 if typ=='SCALAR' else 5126,'count':len(a),'type':typ}
    if not accessors:acc.update(min=xyz.min(axis=0).tolist(),max=xyz.max(axis=0).tolist())
    accessors.append(acc)
image=io.BytesIO();Image.new('RGB',(1,1),(140,140,140)).save(image,format='PNG');image_view=add(image.getvalue())
g={'asset':{'version':'2.0','generator':'Local planar UV patches on unchanged compact screened-Poisson surface'},'extensionsUsed':['KHR_materials_unlit'],'buffers':[{'byteLength':offset}],'bufferViews':views,'accessors':accessors,'images':[{'bufferView':image_view,'mimeType':'image/png'}],'samplers':[{'wrapS':33071,'wrapT':33071,'magFilter':9729,'minFilter':9987}],'textures':[{'source':0,'sampler':0}],'materials':[{'doubleSided':True,'pbrMetallicRoughness':{'baseColorTexture':{'index':0},'metallicFactor':0,'roughnessFactor':1},'extensions':{'KHR_materials_unlit':{}}}],'meshes':[{'primitives':[{'attributes':{'POSITION':0,'NORMAL':1,'TEXCOORD_0':2},'indices':3,'material':0,'mode':4}]}],'nodes':[{'mesh':0}],'scenes':[{'nodes':[0]}],'scene':0}
j=json.dumps(g,separators=(',',':')).encode();j+=b' '*((-len(j))%4);binary=b''.join(buffers);total=12+8+len(j)+8+len(binary);file=OUT/'surface-uncompressed.glb';file.write_bytes(struct.pack('<III',0x46546c67,2,total)+struct.pack('<II',len(j),0x4e4f534a)+j+struct.pack('<II',len(binary),0x004e4942)+binary)
shutil.copyfile(W/'poisson-pilot/photo-bake-implementation.py',OUT/'photo-bake-implementation.py')
audit={'method':'Dominant normal-axis local planar UV projection with .5-unit spatial patches, then UV-only atlas packing. No global conformal solve.','sourceSurface':'poisson-pilot/surface-compact.npz','geometryChangedByUV':False,'normalizedNormals':True,'faces':len(f),'vertices':len(xyz),'patchGroups':len(unique),'atlasWidth':atlas.width,'atlasHeight':atlas.height,'seconds':time.monotonic()-started,'bytes':total,'requiresPhotographicAndSeamReview':True};(OUT/'unwrap-audit.json').write_text(json.dumps(audit,indent=2));print(json.dumps(audit,indent=2),flush=True)
