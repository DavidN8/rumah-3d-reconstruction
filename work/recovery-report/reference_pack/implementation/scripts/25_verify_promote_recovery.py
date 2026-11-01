"""Verify actual v2 delivery assets, then promote a reviewed local derivative."""
import argparse,copy,json,hashlib,shutil
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation
from importlib.machinery import SourceFileLoader
from reconstruction_frame import read_glb,accessor
from colmap_io import read_model,qvec_to_rotmat
core=SourceFileLoader('component_core',str(Path(__file__).with_name('20_component_recovery.py'))).load_module()
BASE,RUN=core.BASE,core.RUN

def texture_hashes(d,b):
    result=[]
    for image in d['images']:
        v=d['bufferViews'][image['bufferView']];payload=b[v.get('byteOffset',0):v.get('byteOffset',0)+v['byteLength']]
        result.append(hashlib.sha256(payload).hexdigest())
    return result

def verify(variant='compact',tag='',packed=False):
    if variant not in ['raw','fast','compact'] or (tag and not tag.replace('-','').isalnum()):raise ValueError('Invalid candidate')
    prefix=tag+'-' if tag else '';stage=prefix+variant
    path=RUN/f'exports/apartment-{stage}.glb';d,b=read_glb(path)
    actual=RUN/f'exports/apartment-{stage}-packed.glb' if packed else path
    if packed:
        record=json.loads(Path(str(actual)+'.compression.json').read_text(encoding='utf-8'))
        assert record['sourceSha256']==core.sha(path) and record['packedSha256']==core.sha(actual)
        assert record['allGeometryBytesRoundTripIdentical'] and record['textureBytesPreserved'] and not record['quantization']
        stage+='-packed'
    meta=json.loads((RUN/f'review/{stage}/cameras.json').read_text(encoding='utf-8'))
    tf=json.loads((RUN/'analysis/component-transforms.json').read_text(encoding='utf-8'))
    assert len(d['meshes'])==2 and len(d['images'])==2
    for node in d['nodes']:
        assert not any(k in node for k in ['translation','rotation','scale'])
        if 'matrix' in node:assert np.allclose(np.array(node['matrix']).reshape(4,4),np.eye(4))
    tris=0;bounds=[];mesh_records=[]
    for mesh in d['meshes']:
        count=0
        for prim in mesh['primitives']:
            p=accessor(d,b,prim['attributes']['POSITION']);n=accessor(d,b,prim['attributes']['NORMAL']);uv=accessor(d,b,prim['attributes']['TEXCOORD_0']);ind=accessor(d,b,prim['indices'])
            assert np.isfinite(p).all() and np.isfinite(n).all() and np.isfinite(uv).all() and ind.max()<len(p)
            count+=ind.size//3;bounds.append([p.min(0),p.max(0)])
        mesh_records.append({'component':mesh['name'],'triangles':count});tris+=count
    assert tris==meta['triangles'] and actual.stat().st_size==meta['fileBytes']
    assert len(meta['cameras'])==501
    cams={c['name']:c for c in meta['cameras']};error=0.;rot_error=0.;native_textures=[]
    for z,name in enumerate(['zone-kitchen','zone-living-bedroom']):
        nc,ni,np3=read_model(BASE/f'colmap-gpu/ws/sparse/{z}')
        rec=tf['components'][z];ss=rec['scale'];rr=np.array(rec['R']);tt=np.array(rec['t'])
        assert abs(np.linalg.det(rr)-1)<1e-8
        for im in ni.values():
            out=cams[im['name']];assert out['zone']==name and out['component']==z
            ro=qvec_to_rotmat(im['qvec']);rn=np.array(out['R_world_to_opencv']);tn=np.array(out['t_world_to_opencv'])
            assert np.allclose(rn,ro@rr.T,atol=1e-10)
            ids=im['point3D_ids'];ids=ids[ids>=0][:24]
            pp=np.array([np3[int(pid)]['xyz'] for pid in ids]);pn=ss*pp@rr.T+tt
            x=pp@ro.T+im['tvec'];xn=pn@rn.T+tn
            if len(pp):error=max(error,float(np.max(np.abs(x/x[:,2,None]-xn/xn[:,2,None]))*max(nc[im['camera_id']]['params'][:2])))
            camera_r=Rotation.from_quat(out['quaternion']).as_matrix();rot_error=max(rot_error,float(np.max(np.abs(camera_r-rn.T@np.diag([1.,-1,-1])))))
        native_name='zone-living-bedroom-allviews' if tag=='allviews' and name=='zone-living-bedroom' else name
        nd,nb=read_glb(RUN/f'exports/{native_name}/{native_name}.glb');native_textures+=texture_hashes(nd,nb)
        if variant=='raw':
            for native_mesh,merged_mesh in zip(nd['meshes'],[d['meshes'][z]]):
                for np_,mp in zip(native_mesh['primitives'],merged_mesh['primitives']):
                    for key in ['POSITION','NORMAL','TEXCOORD_0']:
                        assert np.array_equal(accessor(nd,nb,np_['attributes'][key]),accessor(d,b,mp['attributes'][key]))
                    assert np.array_equal(accessor(nd,nb,np_['indices']),accessor(d,b,mp['indices']))
    assert error<1e-6 and rot_error<1e-10
    assert native_textures==texture_hashes(d,b)
    deviations=[] if variant=='raw' else ([json.loads((RUN/f'analysis/{prefix}fast-deviation-summary.json').read_text(encoding='utf-8'))] if variant=='fast' else [json.loads((RUN/f'analysis/{name}-simplification-gate.json').read_text(encoding='utf-8')) for name in ['zone-kitchen','zone-living-bedroom']])
    sampled_gate=all(r['sampled_gate'] for r in deviations)
    depth=json.loads((RUN/f'analysis/verification-{stage}/depth-and-hole-checks.json').read_text(encoding='utf-8'))
    compact=next(r for r in depth['results'] if r['kind']==('raw' if variant=='raw' else 'compact'))
    assert not depth['errors'] and len(compact['views'])==9
    hole_gate=variant=='raw' or all(r['compaction_hole_gate'] for r in compact['views'])
    if variant=='compact':assert sampled_gate and hole_gate
    out={'overall_status':'PARTIAL: reconstructed candidate; visible completeness, registration and delivery constraints require separate acceptance',
         'variant':variant,'stage':stage,
         'mesh':{'triangles':tris,'bytes':actual.stat().st_size,'sha256':core.sha(actual),'components':mesh_records,'file':str(actual),'working_unpacked_file':str(path),'lossless_compression':packed},
         'frame':{'camera_count':len(cams),'original_components':2,'living_bedroom_shared_similarity':True,'local_bedroom_tilt':False,'projection_invariance_max_pixels':error,'camera_quaternion_matrix_error':rot_error},
         'textures':{'native_texture_bytes_preserved':True,'sha256':native_textures,'count':2},
         'compaction':{'sampled_2mm_gate':sampled_gate,'hole_pixel_regression_gate':hole_gate,'maximum_new_hole_fraction':0 if variant=='raw' else max(r['new_hole_pixel_fraction'] for r in compact['views']),
            'native_arrays_preserved_exactly':variant=='raw','deviation_reports':deviations,
            'independent_global_hausdorff_guarantee':False,'units':'approximate metres; no surveyed dimensional accuracy'},
         'budget':{'original_under_120MB':actual.stat().st_size<120000000,'aspirational_under_100MB':actual.stat().st_size<100000000,'original_600k_to_2M_triangles':600000<=tris<=2000000},
         'kitchen_bridge':json.loads((RUN/'analysis/wide-bridge.json').read_text(encoding='utf-8')),
         'limitations':['Visible holes and softened/warped small objects remain; source comparisons must be inspected.','Wider matching did not provide three orthogonal, spatially distributed planes; approximate kitchen join retained.','Depth-layer flags can include legitimate nearby surfaces; they are not proof of every self-intersection.','The 2mm test is area-sampled in both directions, not a certified global or surveyed metric bound.']}
    core.save(RUN/f'analysis/{stage}-verification.json',out)
    if variant=='compact' and not tag and not packed:core.save(RUN/'analysis/final-verification.json',out)
    print(json.dumps({k:v for k,v in out.items() if k not in ['kitchen_bridge','limitations','compaction']},indent=2),flush=True)

def promote(native=False):
    if native:
        decision=json.loads((RUN/'analysis/delivery-decision.json').read_text(encoding='utf-8'))
        assert decision['selection']=='full_native' and decision['size_and_triangle_caps_removed']
        report=json.loads((RUN/'analysis/allviews-raw-verification.json').read_text(encoding='utf-8'))
        assert report['compaction']['native_arrays_preserved_exactly']
        source=RUN/'review/allviews-raw';model=RUN/'exports/apartment-allviews-raw.glb'
        assert core.sha(model)==report['mesh']['sha256']==decision['source_sha256']
        visual=json.loads((RUN/'analysis/architect-review.json').read_text(encoding='utf-8'));assert visual['reviewed_all_eight']
        report.update(overall_status='DELIVERED_FULL_NATIVE; visual fidelity remains partial',variant='native',stage='full-native',delivery=decision)
        report['budget'].update(enforced_limits=False,policy='Delivery size and triangle caps removed by explicit user choice; native geometry selected')
        report['compaction'].update(no_simplification=True,acceptance_basis='Every native position, normal, UV and triangle index preserved exactly; no compaction displacement')
        report['limitations'][-1]='No simplification error is introduced. This does not establish surveyed accuracy or a complete, error-free reconstruction.'
    else:
        report=json.loads((RUN/'analysis/final-verification.json').read_text(encoding='utf-8'));visual=json.loads((RUN/'analysis/final-visual-review.json').read_text(encoding='utf-8'))
        assert visual.get('reviewed_all_eight') and visual.get('promote_improved_candidate')
        assert report['compaction']['sampled_2mm_gate'] and report['compaction']['hole_pixel_regression_gate']
        assert report['budget']['original_under_120MB'] and report['budget']['original_600k_to_2M_triangles']
        source=RUN/'review/compact';model=RUN/'exports/apartment-compact.glb'
    review=BASE/'review'
    dest=review/'models/iphone-full-room.glb';temp=dest.with_name(dest.name+'.recovery.tmp');shutil.copy2(model,temp);temp.replace(dest)
    meta=json.loads((source/'cameras.json').read_text(encoding='utf-8'))
    if native:meta.update(title='iPhone full native reconstruction',qualityMessage='Full native geometry · approximate scale · visible defects remain',delivery='Full native - no simplification, size or triangle delivery cap')
    core.save(review/'cameras.json',meta)
    for p in (source/'sources').glob('*.jpg'):shutil.copy2(p,review/'sources'/p.name)
    dest=BASE/'exports/iphone-full-room.glb';temp=dest.with_name(dest.name+'.recovery.tmp');shutil.copy2(model,temp);temp.replace(dest)
    core.save(BASE/'exports/cameras.json',meta)
    assert core.sha(dest)==report['mesh']['sha256']
    report['published_paths']={'model':str(dest),'http_model':str(review/'models/iphone-full-room.glb'),'cameras':str(review/'cameras.json'),'offline':str(review/'iPhone-Full-Room-preview.html')}
    core.save(review/'models.json',[{'url':'models/iphone-full-room.glb','bounds':meta['bounds'],'units':'approximate metres','up':[0,1,0]}])
    core.save(review/'detail-models.json',[{'url':'models/iphone-full-room.glb',**{k:v for k,v in meta.items() if k!='cameras'}}])
    # Publish corrected cameras/points as a two-calibration COLMAP derivative.
    transforms=json.loads((RUN/'analysis/component-transforms.json').read_text(encoding='utf-8'))
    cameras={};images={};points={};pid_next=1
    for z in (0,1):
        nc,ni,np3=read_model(BASE/f'colmap-gpu/ws/sparse/{z}');cameras[z+1]=next(iter(nc.values()));pm={pid:pid_next+k for k,pid in enumerate(sorted(np3))};pid_next+=len(pm)
        rec=transforms['components'][z];ss=rec['scale'];rr=np.array(rec['R']);tt=np.array(rec['t'])
        for pid,p in np3.items():points[pm[pid]]={**p,'xyz':ss*rr@p['xyz']+tt}
        for im in sorted(ni.values(),key=lambda x:x['name']):
            pose=next(c for c in meta['cameras'] if c['name']==im['name']);q=Rotation.from_matrix(pose['R_world_to_opencv']).as_quat()
            images[len(images)+1]={**im,'camera_id':z+1,'qvec':np.r_[q[3],q[:3]],'tvec':np.array(pose['t_world_to_opencv']),
                'point3D_ids':np.array([pm.get(int(pid),-1) for pid in im['point3D_ids']],dtype=np.int64)}
    target=BASE/'colmap-gpu/corrected/sparse/0';core.write_model(target,cameras,images,points)
    frame={'version':3,'coordinateSystem':'+Y-up, approximate metres; one rigid similarity per original component',
           'originalComponents':['colmap-gpu/ws/sparse/0','colmap-gpu/ws/sparse/1'],'transformFile':'recovery-v2/analysis/component-transforms.json',
           'checkpointDatasets':'recovery-v2/datasets/zone-kitchen and zone-living-bedroom-allviews; legacy zones/zone-* checkpoints remain in their frozen historical frame',
           'pipeline':'scripts/20_component_recovery.py through scripts/25_verify_promote_recovery.py','legacyTemporalExporterRetired':True,'preciseRegistrationVerified':False}
    core.save(target/'FRAME.json',frame)
    active=BASE/'colmap-gpu/merged/sparse/0';assert not list(active.glob('*.bin'))
    for p in target.glob('*.txt'):shutil.copy2(p,active/p.name)
    shutil.copy2(target/'FRAME.json',active/'FRAME.json')
    core.save(BASE/'analysis/fixed-transforms.json',{'version':3,**transforms,'legacyTransformRecord':'backups/before-component-rebuild-20261027/analysis/fixed-transforms.json'})
    core.save(BASE/'exports/merge-report.json',report);core.save(BASE/'analysis/fixed-verification.json',report)
    if native:
        core.save(RUN/'analysis/full-native-verification.json',report);core.save(RUN/'analysis/final-verification.json',report)
        core.save(BASE/'analysis/active-pipeline.json',{'version':3,'legacy_temporal_pipeline_retired':True,'components':['zone-kitchen','zone-living-bedroom'],'one_similarity_per_original_colmap_component':True,'separate_bedroom_tilt':False,'delivery_state':'Full native primary delivery; size/triangle caps removed by explicit user choice','triangles':report['mesh']['triangles'],'bytes':report['mesh']['bytes']})
    print('Promoted component-aligned full native geometry.' if native else 'Promoted accepted compact derivative.',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['verify','promote']);p.add_argument('--candidate',choices=['compact','raw','fast'],default='compact');p.add_argument('--tag',default='');p.add_argument('--packed',action='store_true');a=p.parse_args()
    if a.stage=='verify':verify(a.candidate,a.tag,a.packed)
    else:
        if a.candidate=='raw' and a.tag=='allviews' and not a.packed:promote(native=True)
        elif a.candidate=='compact' and not a.tag and not a.packed:promote()
        else:raise RuntimeError('Promotion requires an accepted compact derivative or the explicitly chosen full native delivery')
