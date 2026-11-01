"""CPU export of upright source crops and exact fresh-scene camera presets.

Uses selected source timestamps and split labels, never a hardcoded 2 fps name
assumption. Requires explicit Y-up normalization evidence for the fresh model.
"""
from pathlib import Path
import argparse,hashlib,json,sys
HERE=Path(__file__).resolve().parent;WORK=HERE.parent.parent
sys.path[:0]=[str(WORK/'osmo-improve-20261031/pydeps'),str(WORK/'osmo-reconstruct-20261031')]
import numpy as np
import cv2
from seed_fisheye import read_model,qvec_to_rotmat
from export_web_cameras import upright_frame,remap_coordinates,source_mask,self_test

def load_selected(path):
    data=json.loads(path.read_text());result={}
    for row in data['selected']:
        name=Path(row['filename']).name
        if name in result:raise ValueError('Duplicate selected filename '+name)
        result[name]=row
    if not data.get('split_assigned'):raise ValueError('Source timestamp splits must be assigned before camera export')
    return result,data

def sparse_bounds(points):
    positions=np.asarray([p['xyz'] for p in points.values()]);positions=positions[np.isfinite(positions).all(axis=1)]
    if not len(positions):raise ValueError('No finite points for real scene framing bounds')
    return [positions.min(axis=0).tolist(),positions.max(axis=0).tolist()]

def verify_normalization(path,model):
    report=json.loads(path.read_text()); model=model.resolve()
    if report.get('applied') is not True:raise ValueError('Normalization must have actually been applied')
    if Path(report.get('output_model','')).resolve()!=model:raise ValueError('Normalization report output model does not match requested dataset')
    transform=report.get('transform',{});declared=transform.get('coordinate_frame','')
    if declared!='+Y up':raise ValueError('Normalization report must explicitly declare +Y up')
    if report.get('old_reconstruction_opened') is not False or report.get('learned_depth_opened') is not False:raise ValueError('Expected fresh independent reconstruction provenance')
    ray_error=report.get('projection_ray_identity_max_error',float('inf'))
    if not np.isfinite(ray_error) or ray_error>1e-8:raise ValueError('Normalization ray invariance check failed')
    rotation=np.asarray(transform.get('rotation'),dtype=float);scale=transform.get('scale',0)
    if rotation.shape!=(3,3) or not np.allclose(rotation@rotation.T,np.eye(3),atol=1e-8) or not np.isclose(np.linalg.det(rotation),1,atol=1e-8) or not np.isfinite(scale) or scale<=0:raise ValueError('Invalid normalization similarity')
    expected={str(Path(name).resolve()).casefold():sha.lower() for name,sha in report.get('written_files_sha256',{}).items()}
    suffix='bin' if (model/'cameras.bin').exists() else 'txt'
    for stem in ['cameras','images','points3D']:
        target=model/(stem+'.'+suffix);recorded=expected.get(str(target).casefold())
        if not recorded or hashlib.sha256(target.read_bytes()).hexdigest()!=recorded:raise ValueError('Model file is not the audited normalized output: '+str(target))
    return report,declared

def export(args):
    normalization,declared=verify_normalization(args.normalization,args.dataset/'sparse/0')
    cameras,images,points=read_model(args.dataset/'sparse/0');selected,selection=load_selected(args.selection)
    candidates=[]
    for im in images.values():
        row=selected.get(Path(im['name']).name)
        if row and (args.split=='all' or row.get('split')==args.split):candidates.append((im,row))
    if not candidates:raise ValueError('No registered fresh cameras match selection/split metadata')
    used=set();presets=[];details=[];args.output.parent.mkdir(parents=True,exist_ok=True)
    photo_dir=args.output.parent/(args.output.stem+'-photos');photo_dir.mkdir(exist_ok=True)
    for number,target in enumerate(float(t) for t in args.times.split(',')):
        ranked=sorted((item for item in candidates if item[0]['id'] not in used),key=lambda item:(abs(item[1]['time_seconds']-target),not item[0]['name'].replace('\\','/').startswith(args.lens+'/')))
        best=None
        for im,row in ranked[:16]:
            camera=cameras[im['camera_id']];r=qvec_to_rotmat(im['qvec']);virtual,q,forward=upright_frame(r)
            mx,my,valid=remap_coordinates(camera,r,virtual,64,64);mask,mask_path=source_mask(args.dataset,im['name'])
            if mask.shape!=(camera['height'],camera['width']):mask=cv2.resize(mask,(camera['width'],camera['height']),interpolation=cv2.INTER_NEAREST)
            sampled=cv2.remap(mask,mx,my,cv2.INTER_NEAREST,borderMode=cv2.BORDER_CONSTANT,borderValue=0);fraction=float(np.mean(valid&(sampled>127)))
            item=(im,row,camera,r,virtual,q,forward,mask,mask_path,fraction)
            if best is None or fraction>best[-1]:best=item
            if fraction>=.85:best=item;break
        im,row,camera,r,virtual,q,forward,mask,mask_path,fraction=best
        if fraction<.45:raise ValueError(f'No valid upright crop near {target}s, fraction={fraction:.3f}')
        used.add(im['id']);size=args.size
        mx,my,valid=remap_coordinates(camera,r,virtual,size,size)
        source=cv2.imread(str(args.dataset/'images'/im['name']))
        if source is None or source.shape[:2]!=(camera['height'],camera['width']):raise ValueError('Image/camera dimension mismatch '+im['name'])
        photo=cv2.remap(source,mx,my,cv2.INTER_LINEAR,borderMode=cv2.BORDER_CONSTANT,borderValue=0)
        valid&=cv2.remap(mask,mx,my,cv2.INTER_NEAREST,borderMode=cv2.BORDER_CONSTANT,borderValue=0)>127;photo[~valid]=0
        center=-r.T@im['tvec'];stem=f'fresh-{number+1:02d}-{im["name"].replace("/","-").rsplit(".",1)[0]}'
        photo_path=photo_dir/(stem+'.jpg');mask_output=photo_dir/(stem+'-valid.png')
        if not cv2.imwrite(str(photo_path),photo,[cv2.IMWRITE_JPEG_QUALITY,94]):raise IOError(photo_path)
        cv2.imwrite(str(mask_output),valid.astype('uint8')*255)
        label=f'Capture {row["time_seconds"]:.2f}s · {row["split"]} source'
        presets.append({'name':im['name'],'label':label,'sourceFile':str(photo_path.resolve()),'sourceImageId':im['id'],'sourceCameraId':im['camera_id'],'sourceTimeSeconds':row['time_seconds'],'sourceFrame':row['source_frame'],'split':row['split'],'position':center.tolist(),'quaternion':q.tolist(),'imageWidth':size,'imageHeight':size,'intrinsics':[size/2]*4})
        details.append({'sourceName':im['name'],'sourceImageId':im['id'],'sourceCameraId':im['camera_id'],'sourceModel':camera['model'],'sourceCalibration':camera['params'].tolist(),'selectedTimestamp':row['time_seconds'],'targetTimestamp':target,'timeOffset':row['time_seconds']-target,'split':row['split'],'validFraction':float(valid.mean()),'sourceMask':str(mask_path),'outputMask':str(mask_output),'forward':forward.tolist()})
    first=presets[0];bounds=sparse_bounds(points);source='actual registered fresh sparse points (navigation framing only)'
    if args.bounds_json:
        supplied=json.loads(args.bounds_json.read_text());bounds=supplied['bounds'];source=str(args.bounds_json.resolve())
    forward=np.array(details[0]['forward']);result={'bounds':bounds,'boundsSource':source,'coordinateFrame':declared,'normalizationEvidence':str(args.normalization.resolve()),'startCamera':{'position':first['position'],'quaternion':first['quaternion']},'homeTarget':(np.array(first['position'])+forward*2).tolist(),'presets':presets}
    args.output.write_text(json.dumps(result,indent=2));report={'cameraMetadata':str(args.output.resolve()),'dataset':str(args.dataset.resolve()),'normalization':normalization,'selectionSource':str(args.selection.resolve()),'splitRequested':args.split,'interpretation':'Upright calibrated virtual pinhole crops from source video. Eval split holds timestamps out from Gaussian training but uses SfM camera estimation from the same video; it is not an independent capture. Fresh world positions are never copied from the old reconstruction.','references':details}
    report['selection_sha256']=hashlib.sha256(args.selection.read_bytes()).hexdigest()
    registered=[]
    for im in images.values():
        row=selected.get(Path(im['name']).name)
        if row is None:raise ValueError('Registered image absent from selection provenance '+im['name'])
        r=qvec_to_rotmat(im['qvec']);registered.append({'name':im['name'],'sourceImageId':im['id'],'sourceCameraId':im['camera_id'],'sourceFrame':row['source_frame'],'sourceTimeSeconds':row['time_seconds'],'split':row['split'],'position':(-r.T@im['tvec']).tolist(),'opencvCameraToWorldRotation':r.T.tolist()})
    pose_index=args.output.with_name(args.output.stem+'-registered-poses.json')
    if pose_index.exists():raise FileExistsError(pose_index)
    pose_index.write_text(json.dumps({'coordinateFrame':declared,'normalizationEvidence':str(args.normalization.resolve()),'singleGlobalSimilarityForAllVisits':True,'poses':registered},indent=2))
    report['all_registered_source_pose_index']=str(pose_index.resolve())
    args.output.with_suffix('.provenance.json').write_text(json.dumps(report,indent=2));print(json.dumps({'output':str(args.output),'references':len(presets),'actualTimes':[p['sourceTimeSeconds'] for p in presets],'splits':[p['split'] for p in presets]},indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--dataset',type=Path);p.add_argument('--selection',type=Path);p.add_argument('--normalization',type=Path);p.add_argument('--output',type=Path);p.add_argument('--bounds-json',type=Path);p.add_argument('--times',default='1,12,20,25,40,52,60');p.add_argument('--split',choices=['all','train','eval'],default='all');p.add_argument('--lens',default='cam0');p.add_argument('--size',type=int,default=1200);p.add_argument('--self-test',action='store_true');a=p.parse_args()
    if a.self_test:self_test()
    else:
        if not all([a.dataset,a.selection,a.normalization,a.output]):p.error('--dataset --selection --normalization --output are required')
        if a.output.exists():raise FileExistsError(a.output)
        export(a)
