from pathlib import Path
import json,hashlib,shutil,gzip,tarfile
ROOT=Path(__file__).parent;PUB=ROOT/'public';PUB.mkdir(exist_ok=True)
IP=Path(r'C:/Users/bombe/OneDrive/Documents/ChatGPT/Ruang Kamare/roomscan-reconstruction/data/20261027_IPHONE_WIDE')
review=IP/'review';meta=json.loads((review/'cameras.json').read_text(encoding='utf-8'))
sha=lambda p:hashlib.file_digest(Path(p).open('rb'),'sha256').hexdigest()
model=review/'models/iphone-full-room.glb';model_sha=sha(model);name='iphone-full-room-'+model_sha[:8]+'.glb'
for filename in ['index.html','room-viewer.bundle.js','cameras.json']:shutil.copy2(review/filename,PUB/filename)
(PUB/'sources').mkdir(exist_ok=True);(PUB/'models').mkdir(exist_ok=True)
for view in meta['presets']:shutil.copy2(review/view['source'],PUB/view['source'])
compressed=PUB/'models'/(name+'.gz')
with model.open('rb') as src,compressed.open('wb') as f:
 with gzip.GzipFile(filename=name,mode='wb',fileobj=f,compresslevel=1,mtime=0) as dest:shutil.copyfileobj(src,dest,8*1024*1024)
(PUB/'robots.txt').write_text('User-agent: *\nDisallow: /\n',encoding='utf-8')
files=[{'path':str(p.relative_to(PUB)).replace('\\','/'),'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(PUB.rglob('*')) if p.is_file()]
manifest={'site':'rumah.shizuku.rest','native_model_file':name,'native_model_sha256':model_sha,'native_model_bytes':model.stat().st_size,'triangles':meta['triangles'],'public_assets':files,'internal_reports_published':False,'password_required':False}
(ROOT/'payload-manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
with tarfile.open(ROOT/'site.tar','w') as archive:
 for p in sorted(PUB.rglob('*')):
  if p.is_file():archive.add(p,arcname=str(p.relative_to(PUB)).replace('\\','/'))
print(json.dumps({'model':name,'native_bytes':model.stat().st_size,'transport_gzip_bytes':compressed.stat().st_size,'tar_bytes':(ROOT/'site.tar').stat().st_size,'tar_sha256':sha(ROOT/'site.tar'),'public_files':len(files)}))
