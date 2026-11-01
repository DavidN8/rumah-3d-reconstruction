from pathlib import Path
import sys,json,io,struct,time
import numpy as np
from PIL import Image
W=Path(__file__).resolve().parent;sys.path.insert(0,str(W.parent/'tsdfdeps'));import xatlas
is_poisson=len(sys.argv)>1 and sys.argv[1]=='poisson'
OUT=W/('poisson-pilot' if is_poisson else 'tsdf-pilot')
if (OUT/'surface-uncompressed.glb').exists():raise FileExistsError('Preserve prior UV surface')
data=np.load(OUT/('surface-compact.npz' if is_poisson else 'surface.npz'));positions=data['positions'];normals=data['normals'].copy();faces=data['faces'];started=time.monotonic()
length=np.linalg.norm(normals,axis=1,keepdims=True)
if not np.isfinite(normals).all() or np.min(length)<=1e-8:raise ValueError('Invalid input normals')
input_normal_range=[float(length.min()),float(length.max())];normals/=length
assert np.max(np.abs(np.linalg.norm(normals,axis=1)-1))<1e-6
area=np.linalg.norm(np.cross(positions[faces[:,1]]-positions[faces[:,0]],positions[faces[:,2]]-positions[faces[:,0]]),axis=1);degenerate=int(np.sum(area<1e-12));faces=faces[area>=1e-12]
atlas=xatlas.Atlas();atlas.add_mesh(positions,faces,normals=normals);options=xatlas.PackOptions();options.resolution=8192 if is_poisson else 4096;options.padding=4
print('Unwrapping',len(faces),'faces; texture target',options.resolution,flush=True)
chart=xatlas.ChartOptions()
if is_poisson:chart.max_chart_area=.5;chart.max_boundary_length=6;options.blockAlign=True
atlas.generate(chart_options=chart,pack_options=options,verbose=True);mapping,indices,uv=atlas[0];xyz=positions[mapping].astype('<f4');normal=normals[mapping].astype('<f4');uv=uv.astype('<f4');indices=indices.astype('<u4').reshape(-1)
buffers=[];views=[];accessors=[];offset=0
def add(payload,target=None):
    global offset
    payload+=b'\0'*((-len(payload))%4);row={'buffer':0,'byteOffset':offset,'byteLength':len(payload)}
    if target:row['target']=target
    views.append(row);buffers.append(payload);offset+=len(payload);return len(views)-1
for a,typ in [(xyz,'VEC3'),(normal,'VEC3'),(uv,'VEC2'),(indices,'SCALAR')]:
    view=add(a.tobytes(),34963 if typ=='SCALAR' else 34962);acc={'bufferView':view,'componentType':5125 if typ=='SCALAR' else 5126,'count':len(a),'type':typ}
    if len(accessors)==0:acc.update(min=xyz.min(axis=0).tolist(),max=xyz.max(axis=0).tolist())
    accessors.append(acc)
image=io.BytesIO();Image.new('RGB',(1,1),(140,140,140)).save(image,format='PNG');image_view=add(image.getvalue())
g={'asset':{'version':'2.0','generator':'Audited trusted-range TSDF pilot'},'extensionsUsed':['KHR_materials_unlit'],'buffers':[{'byteLength':offset}],'bufferViews':views,'accessors':accessors,'images':[{'bufferView':image_view,'mimeType':'image/png'}],'samplers':[{'wrapS':33071,'wrapT':33071,'magFilter':9729,'minFilter':9987}],'textures':[{'source':0,'sampler':0}],'materials':[{'doubleSided':True,'pbrMetallicRoughness':{'baseColorTexture':{'index':0},'metallicFactor':0,'roughnessFactor':1},'extensions':{'KHR_materials_unlit':{}}}],'meshes':[{'primitives':[{'attributes':{'POSITION':0,'NORMAL':1,'TEXCOORD_0':2},'indices':3,'material':0,'mode':4}]}],'nodes':[{'mesh':0}],'scenes':[{'nodes':[0]}],'scene':0}
j=json.dumps(g,separators=(',',':')).encode();j+=b' '*((-len(j))%4);binary=b''.join(buffers);total=12+8+len(j)+8+len(binary);file=OUT/'surface-uncompressed.glb';file.write_bytes(struct.pack('<III',0x46546c67,2,total)+struct.pack('<II',len(j),0x4e4f534a)+j+struct.pack('<II',len(binary),0x004e4942)+binary)
(OUT/'unwrap-audit.json').write_text(json.dumps({'faces':len(indices)//3,'vertices':len(xyz),'atlasWidth':atlas.width,'atlasHeight':atlas.height,'atlasCount':len(atlas),'maxChartArea':chart.max_chart_area,'maxBoundaryLength':chart.max_boundary_length,'blockAlign':options.blockAlign,'inputNormalLengthRange':input_normal_range,'normalsNormalized':True,'zeroAreaFacesRemoved':degenerate,'seconds':time.monotonic()-started,'file':str(file),'bytes':total},indent=2));print('UV prepared',len(indices)//3,'faces',atlas.width,atlas.height,flush=True)
