"""CPU-only old/new pose alignment for review; never alters training or source models.

The old FFmpeg fps=2 filename denotes output time, not exact source exposure time.
Match actual source-image appearance within a local time window before fitting one
global proper similarity. Report all pose residuals; refuse matched-pose export if
the fresh and old trajectories cannot be aligned coherently.
"""
from pathlib import Path
import argparse,hashlib,importlib.util,json,re,sys
import numpy as np
import cv2
HERE=Path(__file__).resolve().parent;WORK=HERE.parent.parent
sys.path[:0]=[str(WORK/'osmo-improve-20261031/pydeps'),str(WORK/'osmo-reconstruct-20261031')]
from scipy.spatial.transform import Rotation
from seed_fisheye import read_model,qvec_to_rotmat
spec=importlib.util.spec_from_file_location('fresh_export',HERE/'export-clean-cameras.py')
fresh=importlib.util.module_from_spec(spec);spec.loader.exec_module(fresh)

def umeyama(source,target):
    """Fit target = scale * rotation @ source + translation, forbidding reflection."""
    source=np.asarray(source,dtype=float);target=np.asarray(target,dtype=float)
    xs=source-source.mean(0);ys=target-target.mean(0)
    if len(xs)<3 or np.linalg.matrix_rank(xs,tol=1e-8)<2:raise ValueError('Degenerate camera center sample')
    covariance=ys.T@xs/len(xs);u,d,vt=np.linalg.svd(covariance)
    signs=np.ones(3);signs[-1]=np.sign(np.linalg.det(u@vt))
    rotation=u@np.diag(signs)@vt;scale=float(np.sum(d*signs)/(np.sum(xs*xs)/len(xs)))
    if not np.isfinite(scale) or scale<=0:raise ValueError('Invalid fitted scale')
    translation=target.mean(0)-scale*rotation@source.mean(0)
    return scale,rotation,translation

def residuals(source,target,fit):
    scale,rotation,translation=fit
    return np.linalg.norm(scale*np.asarray(source)@rotation.T+translation-np.asarray(target),axis=1)

def robust_fit(source,target,threshold,iterations=1200):
    source=np.asarray(source);target=np.asarray(target);rng=np.random.default_rng(20261031)
    best=None
    for _ in range(iterations):
        ids=rng.choice(len(source),3,replace=False)
        try:fit=umeyama(source[ids],target[ids])
        except ValueError:continue
        error=residuals(source,target,fit);inside=error<threshold
        score=(int(inside.sum()),-float(np.median(error[inside])) if inside.any() else -float('inf'))
        if best is None or score>best[0]:best=score,inside
    if best is None or best[1].sum()<3:raise ValueError('Cannot fit nondegenerate similarity')
    inside=best[1]
    for _ in range(6):
        fit=umeyama(source[inside],target[inside]);updated=residuals(source,target,fit)<threshold
        if updated.sum()<3 or np.array_equal(updated,inside):break
        inside=updated
    return fit,inside,residuals(source,target,fit)

def thumb(path):
    image=cv2.imread(str(path),cv2.IMREAD_REDUCED_GRAYSCALE_8)
    if image is None:raise FileNotFoundError(path)
    return cv2.resize(image,(160,160),interpolation=cv2.INTER_AREA).astype(np.float32)

def image_pairs(old_images,new_images,old_dataset,new_dataset,selection,time_window):
    selected,_=fresh.load_selected(selection);new_by_name={im['name'].replace('\\','/'):im for im in new_images.values()}
    yy,xx=np.mgrid[:160,:160];valid=((xx-80)**2+(yy-80)**2<58**2)&(yy<111)
    used=set();cache={};pairs=[];excluded=[]
    ordered=sorted(old_images.values(),key=lambda im:im['name'])
    for old in ordered:
        name=old['name'].replace('\\','/');match=re.fullmatch(r'(cam[01])/frame_(\d+)\.jpg',name)
        if not match:continue
        lens,index=match[1],int(match[2]);nominal=(index-1)/2.
        options=[]
        for basename,row in selected.items():
            new_name=lens+'/'+basename
            if new_name in used or new_name not in new_by_name or abs(row['time_seconds']-nominal)>time_window:continue
            options.append((new_name,row))
        if not options:excluded.append({'old':name,'reason':'No unused registered selected exposure in time window'});continue
        source=thumb(old_dataset/'images'/name);scores=[]
        for new_name,row in options:
            if new_name not in cache:cache[new_name]=thumb(new_dataset/'images'/new_name)
            difference=(source-cache[new_name])[valid]
            scores.append((float(np.sqrt(np.mean(difference**2))),new_name,row))
        scores.sort(key=lambda item:item[0]);rmse,new_name,row=scores[0]
        # Intentionally conservative: reject large appearance mismatch rather than
        # pretending that nominal fps output times denote identical exposures.
        if rmse>18:excluded.append({'old':name,'reason':'Local source match RMSE > 18/255','rmse':rmse});continue
        used.add(new_name);new=new_by_name[new_name]
        ro=qvec_to_rotmat(old['qvec']);rn=qvec_to_rotmat(new['qvec'])
        pairs.append({'oldName':name,'newName':new_name,'oldNominalOutputTime':nominal,'newSourceTime':row['time_seconds'],'newSourceFrame':row['source_frame'],'newSplit':row['split'],'sourceImageRMSE160':rmse,'runnerUpRMSE160':scores[1][0] if len(scores)>1 else None,'oldCenter':-ro.T@old['tvec'],'newCenter':-rn.T@new['tvec'],'oldC2W':ro.T,'newC2W':rn.T})
    return pairs,excluded

def serial(value):
    if isinstance(value,np.ndarray):return value.tolist()
    if isinstance(value,np.generic):return value.item()
    raise TypeError(type(value))

def align(args):
    normalization,_=fresh.verify_normalization(args.normalization,args.new_dataset/'sparse/0')
    _,old_images,_=read_model(args.old_dataset/'sparse/0');_,new_images,_=read_model(args.new_dataset/'sparse/0')
    pairs,excluded=image_pairs(old_images,new_images,args.old_dataset,args.new_dataset,args.selection,args.time_window)
    if len(pairs)<24:raise ValueError('Fewer than 24 source-matched camera pairs; do not align by guesswork')
    old=np.array([p['oldCenter'] for p in pairs]);new=np.array([p['newCenter'] for p in pairs])
    old_diagonal=float(np.linalg.norm(np.ptp(old,axis=0)));threshold=.025*old_diagonal
    fit,inliers,errors=robust_fit(new,old,threshold);scale,rotation,translation=fit
    orientation=np.array([Rotation.from_matrix(p['oldC2W'].T@rotation@p['newC2W']).magnitude()*180/np.pi for p in pairs])
    time_span=float(np.ptp([p['newSourceTime'] for p in pairs]));fraction=float(inliers.mean())
    gates={'at_least_24_pairs':len(pairs)>=24,'source_time_span_at_least_30s':time_span>=30,'center_inlier_fraction_at_least_70pct':fraction>=.7,'all_center_median_below_2pct_diagonal':float(np.median(errors))<=.02*old_diagonal,'all_center_p95_below_5pct_diagonal':float(np.percentile(errors,95))<=.05*old_diagonal,'all_orientation_median_below_5deg':float(np.median(orientation))<=5,'all_orientation_p95_below_15deg':float(np.percentile(orientation,95))<=15}
    for pair,inside,error,angle in zip(pairs,inliers,errors,orientation):pair.update(centerInlier=bool(inside),centerResidualOldSceneUnits=float(error),orientationResidualDegrees=float(angle))
    report={'purpose':'One global new-to-old similarity for visual comparison only; not a geometry correction, seed or training input.','oldDataset':str(args.old_dataset.resolve()),'newDataset':str(args.new_dataset.resolve()),'normalizationEvidence':str(args.normalization.resolve()),'selectionSha256':hashlib.sha256(args.selection.read_bytes()).hexdigest(),'correspondences':'Same lens, local source appearance matched in a +/-'+str(args.time_window)+'s window around nominal old fps=2 output time. These are nearby exposures, not exact simultaneous views. Motion and reconstruction error both contribute to pose residuals.','sourceScope':'Osmo living/dining/bathroom capture; unrelated iPhone kitchen/bedroom excluded.','fit':{'formula':'X_old = scale * rotation @ X_new + translation','scale':scale,'rotation':rotation,'translation':translation,'metricUnitsKnown':False},'statistics':{'pairs':len(pairs),'timeSpanSeconds':time_span,'oldCameraBoundingDiagonal':old_diagonal,'ransacThresholdOldSceneUnits':threshold,'inlierFraction':fraction,'centerMedian':float(np.median(errors)),'centerP95':float(np.percentile(errors,95)),'orientationMedianDegrees':float(np.median(orientation)),'orientationP95Degrees':float(np.percentile(orientation,95))},'gates':gates,'comparisonPoseExportAllowed':all(gates.values()),'pairs':pairs,'excluded':excluded}
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,default=serial,indent=2))
    if args.old_review_cameras and all(gates.values()):
        old_web=json.loads(args.old_review_cameras.read_text());presets=[]
        for preset in old_web['presets']:
            c2w=Rotation.from_quat(preset['quaternion']).as_matrix();center=rotation.T@(np.array(preset['position'])-translation)/scale
            presets.append({**preset,'position':center.tolist(),'quaternion':Rotation.from_matrix(rotation.T@c2w).as_quat().tolist(),'poseProvenance':'Old review pose transformed by measured global trajectory similarity; alignment residuals apply.'})
        result={'purpose':'Matched old/new evaluation cameras only; do not use for fresh website defaults.','alignmentReport':str(args.output.resolve()),'presets':presets}
        output=args.output.with_name(args.output.stem+'-matched-new-cameras.json')
        if output.exists():raise FileExistsError(output)
        output.write_text(json.dumps(result,indent=2))
    print(json.dumps({'output':str(args.output),'statistics':report['statistics'],'comparisonPoseExportAllowed':all(gates.values()),'gates':gates},indent=2))

def self_test():
    rng=np.random.default_rng(9);source=rng.normal(size=(100,3));rotation=Rotation.from_euler('xyz',[15,-30,7],degrees=True).as_matrix();scale=1.7;translation=np.array([1,2,-3.]);target=scale*source@rotation.T+translation
    corrupted=target.copy();corrupted[:15]+=rng.normal(size=(15,3))*5
    fit,inliers,errors=robust_fit(source,corrupted,.01)
    assert int(inliers.sum())==85 and np.max(errors[15:])<1e-12
    assert abs(fit[0]-scale)<1e-12 and np.max(abs(fit[1]-rotation))<1e-12 and np.max(abs(fit[2]-translation))<1e-12
    old_c2w=Rotation.from_euler('xyz',[5,20,10],degrees=True).as_matrix();new_c2w=rotation.T@old_c2w
    old_center=target[25];new_center=rotation.T@(old_center-translation)/scale
    rays=rng.normal(size=(8,3));rays/=np.linalg.norm(rays,axis=1)[:,None]
    world_old=old_center+rays@old_c2w.T;world_new=new_center+(rays@new_c2w.T)/scale
    assert np.max(abs(scale*world_new@rotation.T+translation-world_old))<1e-12
    print(json.dumps({'passed':True,'syntheticOutliersRejected':15,'inverseCameraRayMappingMaxError':float(np.max(abs(scale*world_new@rotation.T+translation-world_old)))},indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['old-dataset','new-dataset','selection','normalization','output','old-review-cameras']:p.add_argument('--'+name,type=Path)
    p.add_argument('--time-window',type=float,default=.6);p.add_argument('--self-test',action='store_true');a=p.parse_args()
    if a.self_test:self_test()
    else:
        if not all([a.old_dataset,a.new_dataset,a.selection,a.normalization,a.output]):p.error('Dataset, selection, normalization and output paths are required')
        if a.output.exists():raise FileExistsError(a.output)
        align(a)
