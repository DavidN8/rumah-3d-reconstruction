"""One-time deep-cleanup migration away from retired web-release dependencies.

Preserves the exact iPhone metadata and binary identities before retired folders
are removed. Does not train, deploy, or modify external capture data.
"""
from pathlib import Path
import hashlib,json,os,shutil

ROOT=Path(__file__).resolve().parents[1]
AUDIT=ROOT/'docs/repo-audit-2026-11-01'
BACKUP=AUDIT/'private-source-backup'
OLD=ROOT/'work/osmo-web-20261031-v3'
MOBILE=ROOT/'work/mobile-20261029'
BASE=MOBILE/'iphone-baseline'

def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def save(path,text):
    if path.exists():
        backup=BACKUP/path.relative_to(ROOT)
        if not backup.exists():backup.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,backup)
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text,encoding='utf-8')

def main():
    if (AUDIT/'baseline-migration.json').exists():raise SystemExit('Migration already recorded; inspect receipt instead of rerunning.')
    report=json.loads((OLD/'build-report.json').read_text(encoding='utf-8'))
    original=json.loads((OLD/'public'/report['manifestName']).read_text(encoding='utf-8'))
    baseline={'build':'iphone-preserved-20261031','models':{k:original['models'][k] for k in ['phone','native']},'cameraSets':{'iphone':original['cameraSets']['iphone']}}
    BASE.mkdir(exist_ok=True)
    save(BASE/'manifest.json',json.dumps(baseline,indent=2))
    assets=set()
    for model in baseline['models'].values():assets.update([model['url'],model['url']+'.gz',model['preview']])
    for p in baseline['cameraSets']['iphone']['presets']+baseline['cameraSets']['iphone']['photos']:
        if p.get('source'):assets.add(p['source'])
    rows=[]
    for name in sorted(assets):
        src=OLD/'public'/name
        if not src.exists() and name.endswith('iphone-full-room-16f8963b.glb.gz'):src=ROOT/'work/hosting/public'/name
        assert src.is_file(),name
        dest=BASE/name;dest.parent.mkdir(parents=True,exist_ok=True)
        if not dest.exists():os.link(src,dest)
        assert sha(src)==sha(dest)
        rows.append({'path':name,'bytes':dest.stat().st_size,'sha256':sha(dest)})
    save(BASE/'asset-files.json',json.dumps({'files':rows,'source':'Exact metadata and inherited payloads from the retired v3 iPhone baseline; hardlinks preserve one underlying payload.'},indent=2))
    save(MOBILE/'legacy-osmo-cameras.json',(OLD/'osmo-cameras.json').read_text(encoding='utf-8'))
    changed=[]
    for phase in ['osmo-clean-20261031','osmo-parity-20261101']:
        prod=ROOT/'work'/phase/'review/production';p=prod/'build.mjs';s=p.read_text(encoding='utf-8')
        s=s.replace("const old=path.join(work,'osmo-web-20261031-v3/public');","const old=path.join(work,'mobile-20261029/iphone-baseline');")
        s=s.replace("const oldBuild=await read(path.join(work,'osmo-web-20261031-v3/build-report.json'));\nconst manifest=await read(path.join(old,oldBuild.manifestName));","const manifest=await read(path.join(old,'manifest.json'));")
        start="for(const file of carried){await hardlink(path.join(old,file),path.join(pub,file));try{await hardlink(path.join(old,file+'.gz'),path.join(pub,file+'.gz'));}catch(e){if(e.code!=='ENOENT')throw e;if(file==='models/iphone-full-room-16f8963b.glb')await hardlink(path.join(work,'hosting/public',file+'.gz'),path.join(pub,file+'.gz'));}}"
        replacement="for(const file of carried){await hardlink(path.join(old,file),path.join(pub,file));try{await hardlink(path.join(old,file+'.gz'),path.join(pub,file+'.gz'));}catch(e){if(e.code!=='ENOENT')throw e;}}"
        assert start in s;s=s.replace(start,replacement)
        s=s.replace("const cameras=await read(path.resolve(here,candidate.cameras));","const cameraFile=path.resolve(here,candidate.cameras);\n const cameras=await read(cameraFile);")
        s=s.replace("sharp(p.sourceFile)","sharp(path.resolve(path.dirname(cameraFile),p.sourceFile))")
        save(p,s);changed.append(str(p.relative_to(ROOT)))
        p=prod/'prepare-deploy.py';s=p.read_text(encoding='utf-8')
        old="old_dir=here.parent.parent.parent/'osmo-web-20261031-v3';old_build=json.loads((old_dir/'build-report.json').read_text(encoding='utf-8'));old=json.loads((old_dir/'public'/old_build['manifestName']).read_text(encoding='utf-8'))"
        assert old in s;s=s.replace(old,"old_dir=here.parent.parent.parent/'mobile-20261029/iphone-baseline';old=json.loads((old_dir/'manifest.json').read_text(encoding='utf-8'))")
        s=s.replace("reference=old_dir/'public'/row['path']","reference=old_dir/row['path']")
        s=s.replace("        if not reference.exists() and row['path']=='models/iphone-full-room-16f8963b.glb.gz':reference=old_dir.parent/'hosting/public'/row['path']\n",'')
        save(p,s);changed.append(str(p.relative_to(ROOT)))
        cam=ROOT/'work'/phase/'review'/('clean-cameras.json' if phase=='osmo-clean-20261031' else 'calibrated-occupied-cameras.json')
        data=json.loads(cam.read_text(encoding='utf-8'))
        for preset in data['presets']:
            if preset.get('sourceFile'):
                source=Path(preset['sourceFile']);assert source.is_file() and source.is_relative_to(ROOT)
                preset['sourceFile']=os.path.relpath(source,cam.parent).replace('\\','/')
        save(cam,json.dumps(data,indent=2));changed.append(str(cam.relative_to(ROOT)))
        cp=prod/'candidate.json';data=json.loads(cp.read_text(encoding='utf-8'))
        for key in ['file','cameras','packingReport']:
            if Path(data[key]).is_absolute():data[key]=os.path.relpath(data[key],prod).replace('\\','/')
        save(cp,json.dumps(data,indent=2));changed.append(str(cp.relative_to(ROOT)))
    for filename in ['server.mjs','assemble-review.py']:
        p=ROOT/'work/osmo-clean-20261031/review'/filename;s=p.read_text(encoding='utf-8')
        s=s.replace('osmo-web-20261031-v3/osmo-cameras.json','mobile-20261029/legacy-osmo-cameras.json')
        s=s.replace("path.join(work,'osmo-web-20261031-v3/public/models/osmo-lite-30ed8cb766.glb')","path.resolve(work,'../outputs/restored-legacy/osmo-lite-30ed8cb766.glb')")
        save(p,s);changed.append(str(p.relative_to(ROOT)))
    (AUDIT/'baseline-migration.json').write_text(json.dumps({'completed':True,'baseline':str(BASE.relative_to(ROOT)),'assetFiles':rows,'modifiedSourceAndMetadata':changed,'backup':'private-source-backup/','externalDataWrites':0,'productionServerWrites':0},indent=2))
    print(json.dumps({'baselineFiles':len(rows),'modifiedFiles':len(changed),'modelsAndIphoneCameraMetadataPreserved':True,'externalWrites':0}))

if __name__=='__main__':main()
