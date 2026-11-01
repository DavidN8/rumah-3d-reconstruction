set -euo pipefail
TASK=/var/lib/vz/rumah-deploy/20261027
cat > "$TASK/update-connector.sh" <<'SCRIPT'
set -euo pipefail
TASK=/var/lib/vz/rumah-deploy/20261027
pct exec 710 -- cp -n /usr/local/bin/cloudflared /usr/local/bin/cloudflared.pre-rumah-update
set +e
pct exec 710 -- timeout 120 /usr/local/bin/cloudflared update --version 2026.10.4
UPDATE_RESULT=$?
set -e
if [ "$UPDATE_RESULT" -ne 0 ] && [ "$UPDATE_RESULT" -ne 11 ]; then
  printf 'Update failed with status %s; preserved original binary.\n' "$UPDATE_RESULT"
  exit "$UPDATE_RESULT"
fi
pct exec 710 -- /usr/local/bin/cloudflared --version
pct exec 710 -- systemctl restart cloudflared
date -Is > "$TASK/connector-updated.done"
SCRIPT
nohup bash "$TASK/update-connector.sh" > "$TASK/update-connector.log" 2>&1 < /dev/null &
printf 'Own connector update process %s\n' "$!"
