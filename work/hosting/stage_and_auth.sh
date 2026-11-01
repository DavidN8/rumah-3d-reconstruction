set -euo pipefail
TASK=/var/lib/vz/rumah-deploy/20261027
test -f "$TASK/container-installed.done"
touch "$TASK/site.tar.partial"
if ! test -f "$TASK/cloudflare-cert-before.pem"; then
  pct pull 700 /root/.cloudflared/cert.pem "$TASK/cloudflare-cert-before.pem"
  chmod 600 "$TASK/cloudflare-cert-before.pem"
  pct exec 700 -- mv /root/.cloudflared/cert.pem /root/.cloudflared/cert.pre-rumah-20261027.pem
fi
cat > "$TASK/cloudflare-login.sh" <<'SCRIPT'
set -euo pipefail
pct exec 700 -- cloudflared tunnel login
SCRIPT
nohup bash "$TASK/cloudflare-login.sh" > "$TASK/cloudflare-login.log" 2>&1 < /dev/null &
printf 'Certificate refresh process started: %s\n' "$!"
