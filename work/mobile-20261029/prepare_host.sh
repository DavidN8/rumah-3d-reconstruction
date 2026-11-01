set -euo pipefail
TASK=/var/lib/vz/rumah-deploy/20261029-mobile
install -d -m 700 "$TASK"
test ! -f "$TASK/deployed.done"
pct config 710 > "$TASK/container-before.txt"
pct exec 710 -- readlink -f /var/www/rumah/current > "$TASK/release-before.txt"
pct pull 710 /etc/nginx/sites-available/rumah "$TASK/nginx-before.conf"
touch "$TASK/site-mobile.tar.partial"
chmod 600 "$TASK/site-mobile.tar.partial"
printf 'Prepared private deployment staging. Previous release: '
cat "$TASK/release-before.txt"
