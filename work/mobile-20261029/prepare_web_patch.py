from pathlib import Path
import json,hashlib,tarfile
w=Path(__file__).parent
b=json.loads((w/'build-report.json').read_text())
names=['index.html',b['manifestName'],b['bundleName']]
items=[]
with tarfile.open(w/'web-v2.tar','w') as tar:
    for name in names:
        p=w/'public'/name;tar.add(p,arcname=name,recursive=False)
        items.append({'path':name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size})
digest=hashlib.sha256((w/'web-v2.tar').read_bytes()).hexdigest()
(w/'web-v2-manifest.json').write_text(json.dumps({'release':'20261029-mobile-v2','tar_sha256':digest,'files':items},indent=2))
script='''set -euo pipefail
TASK=/var/lib/vz/rumah-deploy/20261029-mobile
RELEASE=/var/www/rumah/releases/20261029-mobile-v2
PREVIOUS=/var/www/rumah/releases/20261029-mobile-v1
test ! -f "$TASK/web-v2.done"
test "$(pct exec 710 -- readlink -f /var/www/rumah/current)" = "$PREVIOUS"
echo '__TAR__  /var/lib/vz/rumah-deploy/20261029-mobile/web-v2.tar.partial' | sha256sum -c -
pct exec 710 -- test ! -e "$RELEASE"
pct exec 710 -- cp -al "$PREVIOUS" "$RELEASE"
pct exec 710 -- unlink "$RELEASE/index.html"
pct exec 710 -- tar --no-same-owner --no-same-permissions -xf - -C "$RELEASE" < "$TASK/web-v2.tar.partial"
pct exec 710 -- chmod 0644 __FILES__
pct exec 710 -- bash -c 'cd /var/www/rumah/releases/20261029-mobile-v2 && sha256sum -c -' <<'HASHES'
__CHECKS__
HASHES
pct exec 710 -- test ! -e "$RELEASE/qa-script-failure.html"
pct exec 710 -- ln -s "$RELEASE" /var/www/rumah/current.mobile-v2-next
pct exec 710 -- mv -Tf /var/www/rumah/current.mobile-v2-next /var/www/rumah/current
pct exec 710 -- bash -c 'test "$(curl -fsS http://127.0.0.1/ | sha256sum | cut -d\\  -f1)" = __INDEX__'
date -Is > "$TASK/web-v2.done"
printf 'Mobile startup recovery deployed. Both earlier releases remain available.\\n'
'''.replace('__TAR__',digest).replace('__FILES__',' '.join('/var/www/rumah/releases/20261029-mobile-v2/'+n for n in names)).replace('__CHECKS__','\n'.join(f"{i['sha256']}  {i['path']}" for i in items)).replace('__INDEX__',b['indexSha256'])
(w/'deploy-web-v2.sh').write_text(script)
print(json.dumps({'tar_bytes':(w/'web-v2.tar').stat().st_size,'sha256':digest}))
