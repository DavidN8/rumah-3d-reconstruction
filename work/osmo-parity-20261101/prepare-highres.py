"""Prepare a separate high-resolution dataset; preserve masks, cameras and baseline."""
from pathlib import Path
import json,shutil,subprocess,sys,os,hashlib
W=Path(__file__).resolve().parent;OLD=W.parent/'osmo-clean-20261031'
CAP=Path('C:/Users/bombe/OneDrive/Documents/ChatGPT/Ruang Kamare/roomscan-reconstruction/data/20261031_OSMO360')
SOURCE=CAP/'clean-v3/dataset';BASE=CAP/'clean-v3/explicit-full-v1/dataset';OUT=CAP/'parity-20261101/explicit-1600/dataset'
# Read the executed source path instead of assuming an intermediate folder.
original=json.loads((BASE/'explicit-pinhole-audit.json').read_text());SOURCE=Path(original['sourceDataset'])
script=(OLD/'build_explicit_pinhole.py').read_text()
script=script.replace("cv2.remap(source,mx,my,cv2.INTER_LINEAR", "cv2.remap(source,mx,my,cv2.INTER_LANCZOS4")
(W/'build_explicit_pinhole.py').write_text(script)
if not OUT.exists():
    result=subprocess.run([sys.executable,str(W/'build_explicit_pinhole.py'),'--source',str(SOURCE),'--output',str(OUT),'--size','1600','--subset','all'])
    if result.returncode:raise RuntimeError('High-resolution materialization failed')
new=json.loads((OUT/'explicit-pinhole-audit.json').read_text())
allowed={x['name'] for x in original['views']};actual={x['name'] for x in new['views']}
if allowed-actual:raise ValueError('A baseline view is missing; do not reuse guidance blindly')
extras=actual-allowed
if extras:
    # Higher sampling admits one formerly sub-threshold face. Keep the exact
    # baseline view set for a controlled resolution comparison, without deleting RGB.
    sys.path.insert(0,str(W.parent/'osmo-reconstruct-20261031'))
    import numpy as np
    from seed_fisheye import read_model,write_model_text
    cams,ims,pts=read_model(OUT/'sparse/0');ims={i:im for i,im in ims.items() if im['name'] in allowed}
    pts={i:p for i,p in pts.items() if sum(int(v) in ims for v in p['image_ids'])>=2}
    for p in pts.values():
        keep=np.array([int(v) in ims for v in p['image_ids']]);p['image_ids']=p['image_ids'][keep];p['point2D_idxs']=p['point2D_idxs'][keep];p['track_len']=len(p['image_ids'])
    for im in ims.values():im['point3D_ids']=np.array([v if int(v) in pts else -1 for v in im['point3D_ids']])
    assert OUT.is_relative_to(CAP/'parity-20261101')
    write_model_text(OUT/'sparse/0',cams,ims,pts,overwrite=True)
    (OUT/'explicit-pinhole-materialized-audit.json').write_text(json.dumps(new,indent=2))
    new['views']=[v for v in new['views'] if v['name'] in allowed];new['virtualViews']=len(new['views']);new['trainViews']=sum(v['sourceSplit']=='train' for v in new['views']);new['evalViews']=sum(v['sourceSplit']=='eval' for v in new['views']);new['excludedExtraFacesForControlledComparison']=sorted(extras)
    for rel in new['sha256']:new['sha256'][rel]=hashlib.sha256((OUT/rel).read_bytes()).hexdigest()
    (OUT/'explicit-pinhole-audit.json').write_text(json.dumps(new,indent=2))
for folder in ['depths-trusted','normals-trusted']:
    (OUT/folder).mkdir(exist_ok=True)
    for file in (BASE/folder).glob('*.png'):
        target=OUT/folder/file.name
        if not target.exists():os.link(file,target)
seed=OUT/'seed-dense-train.ply'
if not seed.exists():os.link(BASE/seed.name,seed)
record={'outputDataset':str(OUT),'originalDataset':str(BASE),'size':1600,'interpolation':'Lanczos4 RGB; nearest-neighbour binary masks','views':new['virtualViews'],'sources':new['sourceInputs'],'train':new['trainViews'],'eval':new['evalViews'],'sameViewIdentity':True,'oldCheckpointInitialization':False,'guidancePolicy':'Reuse exact independently cross-time-validated depth/normal rays and dense train-only seed. Geometry map resolution stays 768; explicit RGB and K increase to 1600. No eval geometry reused.','seedSha256':hashlib.sha256(seed.read_bytes()).hexdigest(),'oldFilesModified':False}
(W/'highres-preparation.json').write_text(json.dumps(record,indent=2));print(json.dumps(record,indent=2))
