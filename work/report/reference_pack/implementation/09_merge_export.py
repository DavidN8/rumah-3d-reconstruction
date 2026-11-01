"""Export compact meshes and recorded cameras in one baked, +Y-up frame.

The trained checkpoint datasets are immutable. See analysis/fixed-transforms.json
for the per-zone correction and the explicit limits of doorway registration.
"""
import copy
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import numpy as np
from scipy.spatial.transform import Rotation
from scipy.spatial import cKDTree
from reconstruction_frame import BASE, read_glb, accessor, write_glb, apply_sim,view_support_distances
from colmap_io import read_model, qvec_to_rotmat
from doorway_repair import build_switch_wall,replacement_mask


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--variant',default='optimized-m12')
    parser.add_argument('--candidate',action='store_true')
    parser.add_argument('--surface-policy',choices=['preserve','legacy-trim'],default='preserve')
    args=parser.parse_args()
    if not args.variant.replace('-','').isalnum():parser.error('invalid variant')
    transforms = json.loads((BASE/'analysis/fixed-transforms.json').read_text())
    cameras,images,points=read_model(BASE/'backups/before-fix-20261027/merged/sparse/0')
    repair=build_switch_wall(transforms,cameras,images) if args.surface_policy=='legacy-trim' else None
    support=[[] for _ in range(3)];support_poses=[]
    for im in images.values():
        frame=int(Path(im['name']).stem.split('_')[-1]);z=0 if frame<=1388 else 1 if frame<=4090 else 2
        rot=qvec_to_rotmat(im['qvec']);centre=-rot.T@im['tvec']
        rec=transforms['zones'][f'zone-{z}'];position=apply_sim(centre[None],rec)[0]
        r=rot@np.array(rec['R']).T
        support[z].append(position[[0,2]])
        support_poses.append({'zone':z,'R':r,'t':-r@position})
    support_trees=[cKDTree(p) for p in support]
    final = dict(asset={'version':'2.0','generator':'iPhone upright compact export'}, scene=0,
                 scenes=[{'nodes':[]}], nodes=[], meshes=[], materials=[], images=[], textures=[],
                 samplers=[], accessors=[], bufferViews=[], extensionsUsed=['KHR_materials_unlit'])
    binary=bytearray(); textures=[]; bounds=[]; zone_stats=[]
    def blob(data, target=None):
        binary.extend(b'\0'*((-len(binary))%4));offset=len(binary);binary.extend(data)
        view={'buffer':0,'byteOffset':offset,'byteLength':len(data)}
        if target:view['target']=target
        final['bufferViews'].append(view);return len(final['bufferViews'])-1
    def array(arr, kind, component):
        i=blob(arr.tobytes(),34963 if kind=='SCALAR' else 34962)
        a={'bufferView':i,'componentType':component,'count':len(arr),'type':kind}
        if kind=='VEC3':a.update(min=arr.min(0).tolist(),max=arr.max(0).tolist())
        final['accessors'].append(a);return len(final['accessors'])-1
    for z in range(3):
        name=f'zone-{z}';source=BASE/f'exports/{args.variant}/{name}/{name}.glb'
        doc,data=read_glb(source);rec=transforms['zones'][name];r=np.array(rec['R'])
        assert abs(np.linalg.det(r)-1)<1e-8
        image_offset=len(final['images']);texture_offset=len(final['textures']);sampler_offset=len(final['samplers']);material_offset=len(final['materials'])
        for image in doc.get('images',[]):
            v=doc['bufferViews'][image['bufferView']];payload=bytes(data[v.get('byteOffset',0):v.get('byteOffset',0)+v['byteLength']])
            vi=blob(payload);final['images'].append({'bufferView':vi,'mimeType':image.get('mimeType','image/jpeg')})
            textures.append({'zone':name,'bufferView':vi,'sha256':hashlib.sha256(payload).hexdigest()})
        final['samplers'].extend(copy.deepcopy(doc.get('samplers',[])))
        for texture in doc.get('textures',[]):
            t=copy.deepcopy(texture);t['source']+=image_offset
            if 'sampler' in t:t['sampler']+=sampler_offset
            final['textures'].append(t)
        for mat in doc['materials']:
            m=copy.deepcopy(mat);p=m.setdefault('pbrMetallicRoughness',{})
            for field in ('baseColorTexture','metallicRoughnessTexture'):
                if field in p:p[field]['index']+=texture_offset
            for field in ('normalTexture','occlusionTexture','emissiveTexture'):
                if field in m:m[field]['index']+=texture_offset
            m['name']=name+' / baked 8K';m['doubleSided']=True;m.setdefault('extensions',{})['KHR_materials_unlit']={}
            p['metallicFactor']=0;p['roughnessFactor']=1;final['materials'].append(m)
        prims=[];tris=0;zonebounds=[];removed=0
        for mesh in doc['meshes']:
            for prim in mesh['primitives']:
                original=accessor(doc,data,prim['attributes']['POSITION'])
                pos=apply_sim(original,rec)
                faces=accessor(doc,data,prim['indices']).reshape(-1,3)
                centres=pos[faces].mean(1)
                # Default: retain every source surface. Camera proximity and
                # frustum inclusion are not proof that a polygon is debris.
                keep=np.ones(len(faces),dtype=bool)
                if args.surface_policy=='legacy-trim':
                    distances=view_support_distances(centres,support_poses)
                    # Keep surfaces with no near competing camera rather than
                    # aggressively cutting the camera-path Voronoi boundary.
                    unknown=~np.isfinite(distances).any(0)
                    if unknown.any():
                        fallback=np.stack([tree.query(centres[unknown][:,[0,2]])[0] for tree in support_trees])
                        distances[:,unknown]=fallback
                    # Keep shared support in a narrow seam band; discard speculative
                    # geometry that belongs inside another trained room.
                    keep=(distances[z]<=distances.min(0)+.12)&(centres[:,1]>-.12)&(centres[:,1]<3.4)
                    if z in (0,1):keep &= ~replacement_mask(pos,faces,repair)
                removed+=int((~keep).sum());faces=faces[keep]
                used,inverse=np.unique(faces,return_inverse=True)
                attrs={}
                for attr,ai in prim['attributes'].items():
                    aa=doc['accessors'][ai];arr=accessor(doc,data,ai)[used]
                    if attr=='POSITION':
                        arr=apply_sim(arr,rec).astype('<f4');bounds.append([arr.min(0),arr.max(0)]);zonebounds.append([arr.min(0),arr.max(0)])
                    elif attr in ('NORMAL','TANGENT'):
                        arr[:,:3]=arr[:,:3]@r.T
                    attrs[attr]=array(arr,aa['type'],aa['componentType'])
                inds=inverse.reshape(-1,1).astype('<u4');tris+=inds.size//3
                prims.append({'attributes':attrs,'indices':array(inds,'SCALAR',5125),
                              'material':prim.get('material',0)+material_offset,'mode':4})
        final['meshes'].append({'name':name,'primitives':prims});final['nodes'].append({'name':name,'mesh':z})
        final['scenes'][0]['nodes'].append(z)
        zone_stats.append({'zone':name,'triangles':tris,'speculative_or_outside_triangles_removed':removed,'source':str(source),'baked_transform':rec,
                           'bounds':[np.min([p[0] for p in zonebounds],0).tolist(),np.max([p[1] for p in zonebounds],0).tolist()]})
    if repair is not None:
        image_index=len(final['images']);texture_index=len(final['textures']);material_index=len(final['materials'])
        view=blob(repair['payload']);final['images'].append({'bufferView':view,'mimeType':'image/jpeg'})
        textures.append({'zone':'doorway-repair','bufferView':view,'sha256':repair['report']['source_sha256']})
        final['samplers'].append({'magFilter':9729,'minFilter':9987,'wrapS':33071,'wrapT':33071})
        final['textures'].append({'source':image_index,'sampler':len(final['samplers'])-1})
        final['materials'].append({'name':'Observed doorway switch wall / planar completion','doubleSided':True,
            'pbrMetallicRoughness':{'baseColorTexture':{'index':texture_index},'metallicFactor':0,'roughnessFactor':1},
            'extensions':{'KHR_materials_unlit':{}}})
        final['meshes'][1]['primitives'].append({'attributes':{'POSITION':array(repair['vertices'],'VEC3',5126),
            'NORMAL':array(repair['normals'],'VEC3',5126),'TEXCOORD_0':array(repair['uv'],'VEC2',5126)},
            'indices':array(repair['faces'].reshape(-1,1),'SCALAR',5125),'material':material_index,'mode':4,
            'extras':repair['report']})
        zone_stats[1]['triangles']+=len(repair['faces'])
    bb=[np.min([p[0] for p in bounds],0).tolist(),np.max([p[1] for p in bounds],0).tolist()]
    # Bake horizontal centering as well. Floor Y remains exactly unchanged.
    shift=np.array([(bb[0][0]+bb[1][0])/2,0.,(bb[0][2]+bb[1][2])/2])
    if np.linalg.norm(shift)>1e-5 and not args.candidate:
        for mesh in final['meshes']:
            for prim in mesh['primitives']:
                ai=prim['attributes']['POSITION'];p=accessor(final,binary,ai,copy=False);p-=shift.astype('<f4')
                final['accessors'][ai].update(min=p.min(0).tolist(),max=p.max(0).tolist())
        for rec in transforms['zones'].values():rec['t']=(np.array(rec['t'])-shift).tolist()
        transforms['global']['t']=(np.array(transforms['global']['t'])-shift).tolist()
        transforms['horizontal_centering_shift']=shift.tolist()
        for zone in zone_stats:zone['bounds']=(np.array(zone['bounds'])-shift).tolist()
        bb=(np.array(bb)-shift).tolist()
    final['extras']={'units':'approximate metres','up':[0,1,0],'floorY':0,'frame':'baked, no root transform',
                     'metricScale':transforms['metric_scale'],'limitations':transforms['limitations']}
    out=BASE/'exports'/('candidate-'+args.variant+'.glb' if args.candidate else 'iphone-full-room.glb');write_glb(out,final,binary)
    checked,raw=read_glb(out)
    for texture in textures:
        bv=checked['bufferViews'][texture['bufferView']];payload=raw[bv['byteOffset']:bv['byteOffset']+bv['byteLength']]
        assert hashlib.sha256(payload).hexdigest()==texture['sha256']
    triangles=0
    for mesh in checked['meshes']:
        for prim in mesh['primitives']:
            idx=accessor(checked,raw,prim['indices']);assert int(idx.max())<checked['accessors'][prim['attributes']['POSITION']]['count'];triangles+=idx.size//3
    if args.candidate:
        (BASE/'analysis'/('candidate-'+args.variant+'.json')).write_text(json.dumps({'triangles':triangles,'file_bytes':out.stat().st_size,'zones':zone_stats,
            'size_gate':600000<=triangles<=2000000 and out.stat().st_size<120000000},indent=2))
        print('Candidate',triangles,'triangles,',round(out.stat().st_size/1e6,2),'MB',flush=True)
        return 0
    assert 600000<=triangles<=2000000
    assert out.stat().st_size<120000000
    (BASE/'analysis/fixed-transforms.json').write_text(json.dumps(transforms,indent=2))
    camera_records=[]
    for im in sorted(images.values(),key=lambda x:x['name']):
        src=int(Path(im['name']).stem.split('_')[-1]);zone=0 if src<=1388 else 1 if src<=4090 else 2
        rec=transforms['zones'][f'zone-{zone}'];rr=np.array(rec['R']);old=qvec_to_rotmat(im['qvec'])
        centre=apply_sim((-old.T@im['tvec'])[None],rec)[0];rot=old@rr.T
        c2w=rr@old.T@np.diag([1.,-1,-1]);quat=Rotation.from_matrix(c2w).as_quat()
        cam=cameras[im['camera_id']]
        camera_records.append({'name':im['name'],'srcFrame':src,'zone':f'zone-{zone}','position':centre.tolist(),
                               'quaternion':quat.tolist(),'forward':(rr@old.T@np.array([0,0,1.])).tolist(),
                               'up':(rr@old.T@np.array([0,-1.,0])).tolist(),'R_world_to_opencv':rot.tolist(),
                               't_world_to_opencv':(-rot@centre).tolist(),
                               'imageWidth':cam['width'],'imageHeight':cam['height'],'intrinsics':cam['params'].tolist(),
                               'source':'sources/'+im['name']})
    choices=[('Kitchen / counter',999),('Kitchen / appliances',903),('Doorway / transition',1398),
             ('Living room',1612),('Living room / windows',2402),('Corridor / bed',3606),('Bedroom / desk',4297),('Bedroom / entrance',4400)]
    presets=[]
    for label,frame in choices:
        chosen=copy.deepcopy(min(camera_records,key=lambda x:abs(x['srcFrame']-frame)));chosen['label']=label;presets.append(chosen)
    start=min(camera_records,key=lambda x:abs(x['srcFrame']-2000))
    seam=[c for c in camera_records if c['srcFrame'] in (1386,1390)]
    home_target=np.mean([c['position'] for c in seam],axis=0).tolist()
    metadata={'version':2,'coordinateFrame':'+Y up, approximate metres, floor Y=0','bounds':bb,'cameras':camera_records,
              'presets':presets,'startCamera':start,'homeTarget':home_target,'triangles':triangles,'fileBytes':out.stat().st_size,
              'bridgeVerified':False,'metricScale':transforms['metric_scale']}
    (BASE/'exports/cameras.json').write_text(json.dumps(metadata,separators=(',',':')))
    review=BASE/'review';(review/'models').mkdir(exist_ok=True);(review/'sources').mkdir(exist_ok=True)
    shutil.copy2(out,review/'models/iphone-full-room.glb')
    (review/'cameras.json').write_text(json.dumps(metadata,separators=(',',':')))
    (review/'detail-models.json').write_text(json.dumps([{'url':'models/iphone-full-room.glb',**{k:v for k,v in metadata.items() if k!='cameras'}}],indent=2))
    (review/'models.json').write_text(json.dumps([{'url':'models/iphone-full-room.glb','bounds':bb,'units':'approximate metres','up':[0,1,0]}],indent=2))
    for p in presets:shutil.copy2(BASE/'frames'/p['name'],review/'sources'/p['name'])
    # The exact +Y-up cameras are also available as a real COLMAP text model.
    sparse=BASE/'colmap-gpu/corrected/sparse/0';sparse.mkdir(parents=True,exist_ok=True)
    shutil.copy2(BASE/'backups/before-fix-20261027/merged/sparse/0/cameras.txt',sparse/'cameras.txt')
    lines=[]
    bedroom_ids=set(read_model(BASE/'zones/zone-2/sparse/0')[2])
    for i,c in enumerate(camera_records,1):
        quat=Rotation.from_matrix(c['R_world_to_opencv']).as_quat();qwxyz=np.r_[quat[3],quat[:3]]
        lines.append(str(i)+' '+' '.join(map(repr,qwxyz.tolist()+c['t_world_to_opencv']))+' 1 '+c['name']+'\n')
    (sparse/'images.txt').write_text('\n'.join(lines)+'\n')
    # Sparse point ownership follows the original split, not arbitrary nearest images.
    old_merge=json.loads((BASE/'backups/before-fix-20261027/model-merge.json').read_text())
    native=[read_model(BASE/f'colmap-gpu/ws/sparse/{i}')[2] for i in (0,1)];off=max(native[1])+1
    lines=[]
    for pid,p in points.items():
        if pid>=off:z=0
        else:z=2 if pid in bedroom_ids else 1
        rec=transforms['zones'][f'zone-{z}'];pp=apply_sim(p['xyz'][None],rec)[0]
        lines.append(f"{pid} "+' '.join(map(repr,pp.tolist()))+' '+' '.join(map(str,p['rgb']))+f" {p['error']}")
    (sparse/'points3D.txt').write_text('\n'.join(lines)+'\n')
    frame={'version':2,'coordinateSystem':'+Y-up, approximate metres, floor Y=0',
           'sourceFrame':'backups/before-fix-20261027/merged/sparse/0',
           'checkpointDatasets':'zones/zone-0, zone-1, zone-2 remain in their preserved legacy training frame',
           'transformFile':'analysis/fixed-transforms.json'}
    (sparse/'FRAME.json').write_text(json.dumps(frame,indent=2))
    active=BASE/'colmap-gpu/merged/sparse/0'
    if list(active.glob('*.bin')):raise RuntimeError('Refusing mixed binary/text active sparse model')
    for name in ('cameras.txt','images.txt','points3D.txt','FRAME.json'):
        shutil.copy2(sparse/name,active/name)
    report={'triangles':triangles,'file_bytes':out.stat().st_size,'bounds':bb,'zones':zone_stats,'textures':textures,
            'texture_bytes_verified':True,'index_bounds_verified':True,'baked_proper_rotations':True,
            'camera_count':len(camera_records),'surface_policy':args.surface_policy,
            'kitchen_bridge':transforms['kitchen_bridge'],'doorway_repair':repair['report'] if repair is not None else {'applied':False,'reason':'Preserve all observed compact-mesh surfaces; inferred patch and destructive replacement disabled'}}
    (BASE/'exports/merge-report.json').write_text(json.dumps(report,indent=2))
    print('Exported',triangles,'triangles,',round(out.stat().st_size/1e6,2),'MB; cameras',len(camera_records),flush=True)
    return 0


if __name__=='__main__':raise SystemExit(main())
