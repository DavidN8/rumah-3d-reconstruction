set -euo pipefail
TASK=/var/lib/vz/rumah-deploy/20261029-mobile
RELEASE=/var/www/rumah/releases/20261029-mobile-v2
PREVIOUS=/var/www/rumah/releases/20261029-mobile-v1
test ! -f "$TASK/web-v2.done"
test "$(pct exec 710 -- readlink -f /var/www/rumah/current)" = "$PREVIOUS"
echo 'f73e4ae0cc62b8cb3fd7609654e6fe3efadef0aab5ded32212201dfd03c3d0d1  /var/lib/vz/rumah-deploy/20261029-mobile/web-v2.tar.partial' | sha256sum -c -
pct exec 710 -- test ! -e "$RELEASE"
pct exec 710 -- cp -al "$PREVIOUS" "$RELEASE"
pct exec 710 -- unlink "$RELEASE/index.html"
pct exec 710 -- tar --no-same-owner --no-same-permissions -xf - -C "$RELEASE" < "$TASK/web-v2.tar.partial"
pct exec 710 -- chmod 0644 /var/www/rumah/releases/20261029-mobile-v2/index.html /var/www/rumah/releases/20261029-mobile-v2/room-9605351002.json /var/www/rumah/releases/20261029-mobile-v2/room-viewer-9d561f9f03.js
pct exec 710 -- bash -c 'cd /var/www/rumah/releases/20261029-mobile-v2 && sha256sum -c -' <<'HASHES'
db33758e0ce3e5d53ec4ef8c35da9b58afefb73d7c61362bd4efe6efb112c8f6  index.html
9605351002b147501bf8e95f3255441c25ca5e0bc3a4a67001842772b2b51fbe  room-9605351002.json
9d561f9f032ea42d64447a734887ce3d5c4b92a3ee06f684a05ffc3e7900012c  room-viewer-9d561f9f03.js
HASHES
pct exec 710 -- test ! -e "$RELEASE/qa-script-failure.html"
pct exec 710 -- ln -s "$RELEASE" /var/www/rumah/current.mobile-v2-next
pct exec 710 -- mv -Tf /var/www/rumah/current.mobile-v2-next /var/www/rumah/current
pct exec 710 -- bash -c 'test "$(curl -fsS http://127.0.0.1/ | sha256sum | cut -d\  -f1)" = db33758e0ce3e5d53ec4ef8c35da9b58afefb73d7c61362bd4efe6efb112c8f6'
date -Is > "$TASK/web-v2.done"
printf 'Mobile startup recovery deployed. Both earlier releases remain available.\n'
