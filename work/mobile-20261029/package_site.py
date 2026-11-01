from pathlib import Path
import json,hashlib,tarfile
w=Path(__file__).parent
report=json.loads((w/'build-report.json').read_text())
phone=json.loads((w/'phone-asset-report.json').read_text())
meta=json.loads((w/'public'/report['manifestName']).read_text())
files=['index.html','robots.txt',report['manifestName'],report['bundleName'],report['overviewName'],phone['phoneFile'],phone['phoneFile']+'.gz']+[x['source'] for x in meta['cameraData']['presets']]
manifest=[]
for relative in files:
    p=w/'public'/relative
    manifest.append({'path':relative,'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
with tarfile.open(w/'site-mobile.tar','w',format=tarfile.PAX_FORMAT) as tar:
    for relative in files:tar.add(w/'public'/relative,arcname=relative,recursive=False)
out={'release':'20261029-mobile-v1','files':manifest,'tar_bytes':(w/'site-mobile.tar').stat().st_size,'tar_sha256':hashlib.sha256((w/'site-mobile.tar').read_bytes()).hexdigest(),'native_model_sha256':'16f8963b043a766317497ee4281f4cf39c6b2190fafaaed51334734723c8b207','phone_model_sha256':phone['sha256']}
(w/'deployment-manifest.json').write_text(json.dumps(out,indent=2))
print(json.dumps({k:v for k,v in out.items() if k!='files'}))
