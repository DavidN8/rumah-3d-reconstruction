"""Verify the scaled RGB rebuild preserved the audited scene and guidance."""
from pathlib import Path
import sys,json,hashlib,time
import numpy as np
W=Path(__file__).resolve().parent;ROOT=W.parent
sys.path[:0]=[str(ROOT/'osmo-improve-20261031/pydeps'),str(ROOT/'osmo-reconstruct-20261031')]
from seed_fisheye import read_model,qvec_to_rotmat
CAP=Path('C:/Users/bombe/OneDrive/Documents/ChatGPT/Ruang Kamare/roomscan-reconstruction/data/20261031_OSMO360');base=CAP/'clean-v3/explicit-full-v1/dataset';high=CAP/'parity-20261101/explicit-1600/dataset';train=high.parent/'training/osmo-sharp-1600-full';started=time.monotonic()
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
bc,bi,bp=read_model(base/'sparse/0');hc,hi,hp=read_model(high/'sparse/0');b={x['name']:x for x in bi.values()};h={x['name']:x for x in hi.values()};assert b.keys()==h.keys() and len(b)==2219
rotation=translation=Kerror=xyerror=nonduplicate_error=0.;common_observations=old_only=new_only=duplicates=0;worst=[]
for name in b:
    old,new=b[name],h[name];a,c=bc[old['camera_id']],hc[new['camera_id']]
    rotation=max(rotation,float(np.max(np.abs(qvec_to_rotmat(old['qvec'])-qvec_to_rotmat(new['qvec'])))));translation=max(translation,float(np.max(np.abs(old['tvec']-new['tvec']))))
    assert a['model']==c['model']=='PINHOLE' and a['width']==a['height']==1200 and c['width']==c['height']==1600
    Kerror=max(Kerror,float(np.max(np.abs(a['params']/1200-c['params']/1600))))
    # Nearest-neighbor binary masks and a fixed three-pixel edge guard can
    # retain slightly different feature observations at the higher resolution.
    # Compare actual shared point identities, never row numbers or -1 sentinels.
    oi={int(pid):xy for pid,xy in zip(old['point3D_ids'],old['points2D_xy']) if pid>=0};ni={int(pid):xy for pid,xy in zip(new['point3D_ids'],new['points2D_xy']) if pid>=0};common=oi.keys()&ni.keys();old_only+=len(oi.keys()-ni.keys());new_only+=len(ni.keys()-oi.keys());common_observations+=len(common)
    if common:
        shared=list(common);differences=np.max(np.abs(np.asarray([oi[pid] for pid in shared])*4/3-np.asarray([ni[pid] for pid in shared])),axis=1);xyerror=max(xyerror,float(differences.max()))
        if differences.max()>1e-8:
            old_unique,old_counts=np.unique(old['point3D_ids'],return_counts=True);new_unique,new_counts=np.unique(new['point3D_ids'],return_counts=True);ambiguous=set(old_unique[old_counts>1])|set(new_unique[new_counts>1]);duplicates+=len(ambiguous-{ -1 })
            for pid,error in zip(shared,differences):
                if pid not in ambiguous:nonduplicate_error=max(nonduplicate_error,float(error))
                if error>1e-8 and len(worst)<8:worst.append({'image':name,'pointId':pid,'errorPixels':float(error),'duplicatePointIdentityInImage':pid in ambiguous,'oldCoordinates':old['points2D_xy'][old['point3D_ids']==pid].tolist(),'newCoordinates':new['points2D_xy'][new['point3D_ids']==pid].tolist()})
print('Maximum contract differences',{'R':rotation,'t':translation,'normalizedK':Kerror,'scaledXYpixels':xyerror,'nonduplicateXY':nonduplicate_error,'worst':worst[:2]},flush=True)
assert rotation<1e-12 and translation<1e-12 and Kerror<1e-12 and nonduplicate_error<1e-8
assert all(np.array_equal(bp[pid]['xyz'],hp[pid]['xyz']) for pid in bp.keys()&hp.keys())
guidance={}
for folder in ['depths-trusted','normals-trusted']:
    aa={p.relative_to(base/folder).as_posix():p for p in (base/folder).rglob('*') if p.is_file()};bb={p.relative_to(high/folder).as_posix():p for p in (high/folder).rglob('*') if p.is_file()};assert aa.keys()==bb.keys()
    assert all(sha(p)==sha(bb[name]) for name,p in aa.items());guidance[folder]={'files':len(aa),'allHashesIdentical':True}
seed=sha(base/'seed-dense-train.ply');assert seed==sha(high/'seed-dense-train.ply')
transform=json.loads((train/'scene_transform.json').read_text());assert np.allclose(transform['train_from_world']['matrix_4x4'],np.eye(4),rtol=0,atol=1e-12)
baseline=json.loads((W/'baseline-preservation.json').read_text());assert all(sha(Path(x['path']))==x['sha256'] for x in baseline['sourceFiles'])
phones=[]
for key,name,expect in [('fast','iphone-phone-2b811d1241.glb',baseline['iphoneHashes']['fast']),('full','iphone-full-room-16f8963b.glb',baseline['iphoneHashes']['full'])]:
    file=W/'review/production/public/models'/name;actual=sha(file);assert actual==expect;phones.append({'model':key,'file':str(file),'bytes':file.stat().st_size,'sha256':actual,'preserved':True})
report={'passed':True,'views':len(b),'RGBSize':1600,'baselineRGBSize':1200,'maxRotationMatrixError':rotation,'maxTranslationError':translation,'maxNormalizedIntrinsicsError':Kerror,'maxScaledFeatureObservationErrorPixelsWhenPointIDsUnique':nonduplicate_error,'maxErrorWhenDuplicatePointIDsComparedNaively':xyerror,'ambiguousDuplicatePointInstances':duplicates,'duplicateExamples':worst,'sharedObservations':common_observations,'oldOnlyObservations':old_only,'newOnlyObservations':new_only,'observationDifference':'Resolution-dependent mask sampling and fixed three-pixel view-edge guard; repeated point identities cannot be compared by dict row. All shared 3D positions unchanged; exact original dense training seed reused','guidance':guidance,'seedSha256':seed,'trainingTransformIdentity':True,'baselineFilesVerifiedUnchanged':len(baseline['sourceFiles']),'iphoneModels':phones,'seconds':time.monotonic()-started,'scope':'Identity and geometry contract; does not assert visual acceptance or physical mobile compatibility'}
(W/'input-contract-verification.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
