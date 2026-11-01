"""Publish the full native geometry selected explicitly by the human user."""
import json,shutil,datetime
from pathlib import Path
from importlib.machinery import SourceFileLoader
core=SourceFileLoader('publish_core',str(Path(__file__).with_name('20_component_recovery.py'))).load_module()
verify=SourceFileLoader('publish_verify',str(Path(__file__).with_name('25_verify_promote_recovery.py'))).load_module()
BASE,RUN=core.BASE,core.RUN
frozen=RUN/'review/before-rebuild';manifest=frozen/'frozen-baseline.json'
if not manifest.exists():
    (frozen/'models').mkdir(parents=True,exist_ok=True);(frozen/'sources').mkdir(exist_ok=True);files=[]
    for rel in ['index.html','mesh-viewer.html','room-viewer.bundle.js','cameras.json','models/iphone-full-room.glb']:
        p=BASE/'review'/rel;shutil.copy2(p,frozen/rel);files.append({'path':rel,'sha256':core.sha(p),'bytes':p.stat().st_size})
    meta=json.loads((frozen/'cameras.json').read_text(encoding='utf-8'))
    for p in meta['presets']:shutil.copy2(BASE/'review'/p['source'],frozen/p['source'])
    core.save(manifest,{'purpose':'Frozen actual pre-rebuild primary viewer for before/after evidence','files':files})
decision={'selection':'full_native','source':'Explicit human reply to the delivery-choice question','quote':"Full native, I don't mind the bigger size, remove the limitations",'recorded_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'size_and_triangle_caps_removed':True,'geometry_simplification_disabled':True,'source_file':str(RUN/'exports/apartment-allviews-raw.glb'),'source_sha256':core.sha(RUN/'exports/apartment-allviews-raw.glb')}
core.save(RUN/'analysis/delivery-decision.json',decision);verify.promote(native=True)
