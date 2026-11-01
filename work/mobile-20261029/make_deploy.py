from pathlib import Path
import json,re
w=Path(__file__).parent
m=json.loads((w/'deployment-manifest.json').read_text())
assert all(re.fullmatch(r'[a-zA-Z0-9_./-]+',x['path']) and '..' not in x['path'] for x in m['files'])
checks='\n'.join(f"{x['sha256']}  {x['path']}" for x in m['files'])
script=r'''set -euo pipefail
TASK=/var/lib/vz/rumah-deploy/20261029-mobile
RELEASE=/var/www/rumah/releases/20261029-mobile-v1
PREVIOUS=$(cat "$TASK/release-before.txt")
test "$PREVIOUS" = /var/www/rumah/releases/20261027-full-native
test "$(pct exec 710 -- readlink -f /var/www/rumah/current)" = "$PREVIOUS"
test ! -f "$TASK/deployed.done"
echo '__TAR_HASH__  /var/lib/vz/rumah-deploy/20261029-mobile/site-mobile.tar.partial' | sha256sum -c -
pct exec 710 -- test ! -e "$RELEASE"
pct exec 710 -- mkdir -p "$RELEASE/models" "$RELEASE/sources"
pct exec 710 -- tar --no-same-owner --no-same-permissions -xf - -C "$RELEASE" < "$TASK/site-mobile.tar.partial"
pct exec 710 -- find "$RELEASE" -type f -exec chmod 0644 '{}' +
pct exec 710 -- find "$RELEASE" -type d -exec chmod 0755 '{}' +
pct exec 710 -- bash -c 'cd /var/www/rumah/releases/20261029-mobile-v1 && sha256sum -c -' <<'HASHES'
__FILE_CHECKS__
HASHES
for name in iphone-full-room-16f8963b.glb iphone-full-room-16f8963b.glb.gz; do
  pct exec 710 -- ln "$PREVIOUS/models/$name" "$RELEASE/models/$name"
done
for name in cameras.json room-viewer.bundle.js; do
  pct exec 710 -- ln "$PREVIOUS/$name" "$RELEASE/$name"
done
pct exec 710 -- bash -c 'cd /var/www/rumah/releases/20261029-mobile-v1/models; echo "16f8963b043a766317497ee4281f4cf39c6b2190fafaaed51334734723c8b207  iphone-full-room-16f8963b.glb" | sha256sum -c -; test "$(gzip -dc iphone-phone-2b811d1241.glb.gz | sha256sum | cut -d\  -f1)" = 2b811d124120e70dcecc25d06e5dc397e2a28f310403a21fdfa1e290c41c9d2b'
pct exec 710 -- nginx -t
PROMOTED=0
trap 'rc=$?; if [ "$rc" -ne 0 ] && [ "$PROMOTED" -eq 1 ]; then pct exec 710 -- ln -s "$PREVIOUS" /var/www/rumah/current.mobile-rollback; pct exec 710 -- mv -Tf /var/www/rumah/current.mobile-rollback /var/www/rumah/current; echo "Restored previous release after failed origin verification."; fi; exit "$rc"' EXIT
pct exec 710 -- test -L /var/www/rumah/current
pct exec 710 -- ln -s "$RELEASE" /var/www/rumah/current.mobile-next
pct exec 710 -- mv -Tf /var/www/rumah/current.mobile-next /var/www/rumah/current
PROMOTED=1
pct exec 710 -- bash -c 'test "$(curl -fsS http://127.0.0.1/ | sha256sum | cut -d\  -f1)" = __INDEX_HASH__'
pct exec 710 -- curl -fsS -I -H 'Accept-Encoding: gzip' http://127.0.0.1/models/iphone-phone-2b811d1241.glb
pct exec 710 -- systemctl is-active nginx cloudflared
mv "$TASK/site-mobile.tar.partial" "$TASK/site-mobile.tar"
date -Is > "$TASK/deployed.done"
printf 'Mobile release is live; previous release is preserved at %s\n' "$PREVIOUS"
'''
build=json.loads((w/'build-report.json').read_text())
script=script.replace('__TAR_HASH__',m['tar_sha256']).replace('__FILE_CHECKS__',checks).replace('__INDEX_HASH__',build['indexSha256'])
(w/'deploy-mobile.sh').write_text(script,encoding='utf-8')
print('Prepared atomic release with file hashes and rollback checks.')
