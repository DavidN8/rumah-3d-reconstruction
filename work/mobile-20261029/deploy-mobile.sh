set -euo pipefail
TASK=/var/lib/vz/rumah-deploy/20261029-mobile
RELEASE=/var/www/rumah/releases/20261029-mobile-v1
PREVIOUS=$(cat "$TASK/release-before.txt")
test "$PREVIOUS" = /var/www/rumah/releases/20261027-full-native
test "$(pct exec 710 -- readlink -f /var/www/rumah/current)" = "$PREVIOUS"
test ! -f "$TASK/deployed.done"
echo 'a28fbea4575fd6362e8df5167f5f7d7fdc661058e99c882d3d3f2a49cc987b5f  /var/lib/vz/rumah-deploy/20261029-mobile/site-mobile.tar.partial' | sha256sum -c -
pct exec 710 -- test ! -e "$RELEASE"
pct exec 710 -- mkdir -p "$RELEASE/models" "$RELEASE/sources"
pct exec 710 -- tar --no-same-owner --no-same-permissions -xf - -C "$RELEASE" < "$TASK/site-mobile.tar.partial"
pct exec 710 -- find "$RELEASE" -type f -exec chmod 0644 '{}' +
pct exec 710 -- find "$RELEASE" -type d -exec chmod 0755 '{}' +
pct exec 710 -- bash -c 'cd /var/www/rumah/releases/20261029-mobile-v1 && sha256sum -c -' <<'HASHES'
20fd6d960c58539236f88d1d30372ef72f6edcdada9dd6a433d4c947c336c4d4  index.html
331ea9090db0c9f6f597bd9840fd5b171830f6e0b3ba1cb24dfa91f0c95aedc1  robots.txt
b42f3e37c29709c9c08dde7bd010713189e57395aa0d5dd17d389b2d5cf7743b  room-b42f3e37c2.json
c1e65c82a7019de979d94d7144bf92d2441001d42011bb9d573e31c93ccb00e7  room-viewer-c1e65c82a7.js
8516540657f307fcf60a29e2f6eba34186f9f75421139e643fb560f2cc8d6c5c  overview-8516540657.jpg
2b811d124120e70dcecc25d06e5dc397e2a28f310403a21fdfa1e290c41c9d2b  models/iphone-phone-2b811d1241.glb
2683f178656b3c6c48a05a49812ecc3d62bd46bfb16989045c41c66708e570ca  models/iphone-phone-2b811d1241.glb.gz
3af470bb2687de65bb8f574f06348a7ebda7dc6302bce7aa8f5c49515d1854eb  sources/frame_0000999.jpg
544835ade72c22594fbfad011d60e2358579b71922407f7abdf24509439853a0  sources/frame_0000903.jpg
a468d1455616eca37fd99c60cfe22bff7b02eca88b601a60642cb3cfde16aa41  sources/frame_0001398.jpg
43a803084c79304cdc3abef83f42f73c3207bf39d590c7474d752fbbdb233a55  sources/frame_0001612.jpg
8a4cbada269b96b02bca186868eb6c5583565386ebb5352b09e9073c4b48f5dd  sources/frame_0002402.jpg
9aafb22ee5af6a806f432622cdbbb405b5551ad1df69773922c2382cacf94f8a  sources/frame_0003606.jpg
bff0d428b383a592fca70bc5e7de18109fd3c86e1ca7531f1d53f897354bca36  sources/frame_0004297.jpg
e5923f2cef8f1d571329a9767bce8c0e501fefea8926d375a9c58f0d227a9648  sources/frame_0004400.jpg
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
pct exec 710 -- bash -c 'test "$(curl -fsS http://127.0.0.1/ | sha256sum | cut -d\  -f1)" = 20fd6d960c58539236f88d1d30372ef72f6edcdada9dd6a433d4c947c336c4d4'
pct exec 710 -- curl -fsS -I -H 'Accept-Encoding: gzip' http://127.0.0.1/models/iphone-phone-2b811d1241.glb
pct exec 710 -- systemctl is-active nginx cloudflared
mv "$TASK/site-mobile.tar.partial" "$TASK/site-mobile.tar"
date -Is > "$TASK/deployed.done"
printf 'Mobile release is live; previous release is preserved at %s\n' "$PREVIOUS"
