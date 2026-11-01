"""Read back the published camera model and hash the streamed offline asset."""
import json,base64,hashlib
from pathlib import Path
import numpy as np
from colmap_io import read_model,qvec_to_rotmat
from importlib.machinery import SourceFileLoader
core=SourceFileLoader('native_check_core',str(Path(__file__).with_name('20_component_recovery.py'))).load_module()
BASE,RUN=core.BASE,core.RUN
report=json.loads((RUN/'analysis/full-native-verification.json').read_text(encoding='utf-8'));expected=report['mesh']['sha256']
paths=[BASE/'exports/iphone-full-room.glb',BASE/'review/models/iphone-full-room.glb',RUN/'exports/apartment-allviews-raw.glb']
hashes={str(p):core.sha(p) for p in paths};assert all(h==expected for h in hashes.values())
meta=json.loads((BASE/'review/cameras.json').read_text(encoding='utf-8'));byname={c['name']:c for c in meta['cameras']}
cams,ims,pts=read_model(BASE/'colmap-gpu/merged/sparse/0');assert len(cams)==2 and len(ims)==501
rotation_error=translation_error=0
for im in ims.values():
    c=byname[im['name']];assert im['camera_id']==c['component']+1
    rotation_error=max(rotation_error,float(np.max(np.abs(qvec_to_rotmat(im['qvec'])-np.array(c['R_world_to_opencv'])))))
    translation_error=max(translation_error,float(np.max(np.abs(im['tvec']-np.array(c['t_world_to_opencv'])))))
    assert all(int(pid) in pts for pid in im['point3D_ids'] if pid>=0)
assert rotation_error<1e-12 and translation_error<1e-12
start=b'window.ROOM_EMBED.modelChunks.push("';end=b'");document.currentScript.remove();</script>'
pending=b'';inside=False;digest=hashlib.sha256();decoded_bytes=chunks=0
offline=BASE/'review/iPhone-Full-Room-preview.html'
with offline.open('rb') as f:
    while block:=f.read(2*1024*1024):
        pending+=block
        while True:
            if not inside:
                at=pending.find(start)
                if at<0:pending=pending[-len(start):];break
                pending=pending[at+len(start):];inside=True
            at=pending.find(end)
            if at<0:break
            raw=base64.b64decode(pending[:at],validate=True);digest.update(raw);decoded_bytes+=len(raw);chunks+=1
            pending=pending[at+len(end):];inside=False
assert not inside and chunks==18 and decoded_bytes==paths[0].stat().st_size and digest.hexdigest()==expected
out={'primary_glb_hashes':hashes,'all_native_glbs_byte_identical':True,'triangle_count':report['mesh']['triangles'],'model_bytes':paths[0].stat().st_size,'camera_count':len(ims),'calibration_count':len(cams),'sparse_points':len(pts),'colmap_rotation_max_error':rotation_error,'colmap_translation_max_error':translation_error,'offline_html_bytes':offline.stat().st_size,'offline_chunks':chunks,'offline_decoded_bytes':decoded_bytes,'offline_decoded_sha256':digest.hexdigest(),'offline_model_byte_identical':True,'delivery_caps_removed_by_explicit_user_choice':True}
core.save(RUN/'analysis/full-native-integrity.json',out);print(json.dumps(out,indent=2))
