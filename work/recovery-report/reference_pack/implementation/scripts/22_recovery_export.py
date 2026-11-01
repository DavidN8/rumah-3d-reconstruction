"""Stage two component-aligned native meshes; promote only after visual gates."""
import argparse,copy,hashlib,json,shutil
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation
from reconstruction_frame import BASE,read_glb,accessor,write_glb

RUN=BASE/'recovery-v2'

def stage(pilot=False,compact=None,inputs='native',tag='',living_source=None,kitchen_source=None):
    if tag and not tag.replace('-','').isalnum():raise ValueError('Invalid stage tag')
    prefix=(tag+'-') if tag else ''
    names=['zone-kitchen'] if pilot else ['zone-kitchen','zone-living-bedroom']
    path=RUN/'exports'/(('pilot-' if pilot else 'apartment-')+prefix+('raw' if inputs=='native' else inputs)+'.glb')
    if compact:path=Path(compact)
    else:
        d={'asset':{'version':'2.0','generator':'iPhone component recovery v2'},'scene':0,'scenes':[{'nodes':[]}],
           'nodes':[],'meshes':[],'materials':[],'images':[],'textures':[],'samplers':[],'accessors':[],'bufferViews':[],
           'extensionsUsed':['KHR_materials_unlit'],'extras':{'frame':'+Y up; approximate metres','componentAligned':True,'oneLivingBedroomTransform':True,'manualInferredRepairs':False,'nativeSmallHoleFillingMaxEdges':64}}
        binary=bytearray();records=[]
        def blob(data,target=None):
            binary.extend(b'\0'*((-len(binary))%4));v={'buffer':0,'byteOffset':len(binary),'byteLength':len(data)}
            if target:v['target']=target
            binary.extend(data);d['bufferViews'].append(v);return len(d['bufferViews'])-1
        def arr(a,kind,ct):
            v=blob(a.tobytes(),34963 if kind=='SCALAR' else 34962);rec={'bufferView':v,'componentType':ct,'count':len(a),'type':kind}
            if kind=='VEC3':rec.update(min=a.min(0).tolist(),max=a.max(0).tolist())
            d['accessors'].append(rec);return len(d['accessors'])-1
        for name in names:
            suffix={'native':'','compact':'-compact','fast':'-compact-fast'}[inputs]
            source=RUN/f'exports/{name}/{name}{suffix}.glb';doc,data=read_glb(source)
            if name=='zone-living-bedroom' and living_source:
                source=Path(living_source);doc,data=read_glb(source)
            if name=='zone-kitchen' and kitchen_source:
                source=Path(kitchen_source);doc,data=read_glb(source)
            for node in doc['nodes']:
                assert 'rotation' not in node and 'translation' not in node and 'scale' not in node
                if 'matrix' in node:assert np.allclose(np.array(node['matrix']).reshape(4,4),np.eye(4))
            io,to,so,mo=map(lambda k:len(d[k]),['images','textures','samplers','materials'])
            for image in doc['images']:
                v=doc['bufferViews'][image['bufferView']];payload=bytes(data[v.get('byteOffset',0):v.get('byteOffset',0)+v['byteLength']])
                d['images'].append({'bufferView':blob(payload),'mimeType':image.get('mimeType','image/jpeg')})
                records.append({'zone':name,'source':str(source),'texture_sha256':hashlib.sha256(payload).hexdigest(),'texture_bytes':len(payload)})
            d['samplers']+=copy.deepcopy(doc.get('samplers',[]))
            for t in doc.get('textures',[]):
                t=copy.deepcopy(t);t['source']+=io
                if 'sampler' in t:t['sampler']+=so
                d['textures'].append(t)
            for m in doc['materials']:
                m=copy.deepcopy(m);p=m.setdefault('pbrMetallicRoughness',{})
                for k in ['baseColorTexture','metallicRoughnessTexture']:
                    if k in p:p[k]['index']+=to
                for k in ['normalTexture','occlusionTexture','emissiveTexture']:
                    if k in m:m[k]['index']+=to
                m['name']=name;m['doubleSided']=True;m.setdefault('extensions',{})['KHR_materials_unlit']={};p.update(metallicFactor=0,roughnessFactor=1)
                d['materials'].append(m)
            prims=[]
            for mesh in doc['meshes']:
                for p in mesh['primitives']:
                    attrs={k:arr(accessor(doc,data,v),doc['accessors'][v]['type'],doc['accessors'][v]['componentType']) for k,v in p['attributes'].items()}
                    prims.append({'attributes':attrs,'indices':arr(accessor(doc,data,p['indices']).astype('<u4'),'SCALAR',5125),'material':p.get('material',0)+mo,'mode':4})
            index=len(d['meshes']);d['meshes'].append({'name':name,'primitives':prims});d['nodes'].append({'name':name,'mesh':index});d['scenes'][0]['nodes'].append(index)
        write_glb(path,d,binary)
        (RUN/'analysis'/('pilot-export.json' if pilot else prefix+('raw' if inputs=='native' else inputs)+'-export.json')).write_text(json.dumps({'file':str(path),'textures':records,'policy':'No ownership crops, geometry height cuts or manual wall/floor patches. Native extraction includes the specified <=64-edge small-hole fill and floater policy. Native mode preserves every native output face; fast/compact modes are simplification derivatives.'},indent=2),encoding='utf-8')
    d,binary=read_glb(path);points=[];triangles=0
    for m in d['meshes']:
        for p in m['primitives']:
            a=accessor(d,binary,p['attributes']['POSITION']);f=accessor(d,binary,p['indices']);assert f.max()<len(a);triangles+=f.size//3
            points.append(np.array([a.min(0),a.max(0)]))
    bounds=[np.min([a[0] for a in points],0).tolist(),np.max([a[1] for a in points],0).tolist()]
    rows=json.loads((RUN/'analysis/all-source-poses.json').read_text(encoding='utf-8'));cams=[]
    for row in rows:
        r=np.array(row['R']);cam=row['camera'];quat=Rotation.from_matrix(r.T@np.diag([1.,-1,-1])).as_quat()
        cams.append({'name':row['name'],'srcFrame':int(Path(row['name']).stem.split('_')[-1]),'zone':row['zone'],'component':row['component'],
          'position':row['position'],'quaternion':quat.tolist(),'forward':(r.T@np.array([0,0,1.])).tolist(),'up':(r.T@np.array([0,-1.,0])).tolist(),
          'R_world_to_opencv':row['R'],'t_world_to_opencv':row['t'],'imageWidth':cam['width'],'imageHeight':cam['height'],'intrinsics':cam['params'],'source':'sources/'+row['name']})
    choices=[('Kitchen / counter',999),('Kitchen / appliances',903),('Doorway / transition',1398),('Living room',1612),('Living room / windows',2402),('Corridor / bed',3606),('Bedroom / desk',4297),('Bedroom / entrance',4400)]
    presets=[]
    for label,num in choices:
        p=copy.deepcopy(next(a for a in cams if a['srcFrame']==num));p['label']=label;presets.append(p)
    start=presets[0] if pilot else min(cams,key=lambda a:abs(a['srcFrame']-2000))
    metadata={'version':3,'title':'Kitchen pilot - candidate' if pilot else 'iPhone component rebuild','coordinateFrame':'+Y-up approximate metres; one similarity per original component',
              'bounds':bounds,'cameras':cams,'presets':presets,'startCamera':start,'homeTarget':np.mean([p['position'] for p in cams if p['srcFrame'] in [1386,1390]],0).tolist(),
              'triangles':triangles,'fileBytes':path.stat().st_size,'bridgeVerified':False,'metricScale':'Approximate; no survey. Single component-level similarity, no local bedroom tilt.'}
    folder=RUN/'review'/(prefix+('pilot-'+inputs if pilot and inputs!='native' else 'pilot' if pilot else 'compact' if compact else 'raw' if inputs=='native' else inputs));(folder/'models').mkdir(parents=True,exist_ok=True);(folder/'sources').mkdir(exist_ok=True)
    shutil.copy2(path,folder/'models/iphone-full-room.glb');(folder/'cameras.json').write_text(json.dumps(metadata,separators=(',',':')),encoding='utf-8')
    for p in presets:shutil.copy2(BASE/'frames'/p['name'],folder/p['source'])
    (path.with_suffix('.cameras.json')).write_text(json.dumps(metadata,separators=(',',':')),encoding='utf-8')
    print(json.dumps({'staged':str(folder),'model':str(path),'triangles':triangles,'bytes':path.stat().st_size,'bounds':bounds}),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--pilot',action='store_true');parser.add_argument('--compact',type=Path);parser.add_argument('--inputs',choices=['native','compact','fast'],default='native');parser.add_argument('--tag',default='');parser.add_argument('--living-source',type=Path);parser.add_argument('--kitchen-source',type=Path);args=parser.parse_args();stage(args.pilot,args.compact,args.inputs,args.tag,args.living_source,args.kitchen_source)
