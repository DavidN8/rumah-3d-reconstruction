set -euo pipefail
TASK=/var/lib/vz/rumah-deploy/20261027
test -f "$TASK/site-deployed.done"
test -f "$TASK/tunnel-create.log"
pct exec 700 -- cloudflared tunnel list --output json > "$TASK/tunnels-current.json"
UUID=$(python3 - "$TASK/tunnels-current.json" "$TASK/tunnel-create.log" <<'PY'
import json,sys,pathlib
items=[x for x in json.load(open(sys.argv[1])) if x['name']=='rumah' and x.get('deleted_at') in (None,'','0001-01-01T00:00:00Z')]
assert len(items)==1, 'Expected one active rumah tunnel'
uuid=items[0]['id']
assert f'Created tunnel rumah with id {uuid}' in pathlib.Path(sys.argv[2]).read_text(), 'Tunnel must belong to this deployment'
print(uuid)
PY
)
printf '%s\n' "$UUID" > "$TASK/tunnel-id.txt"
pct pull 700 "/root/.cloudflared/$UUID.json" "$TASK/rumah-tunnel.json"
chmod 600 "$TASK/rumah-tunnel.json"
pct pull 700 /bin/cloudflared "$TASK/cloudflared"
pct push 710 "$TASK/cloudflared" /usr/local/bin/cloudflared --perms 0755
pct exec 710 -- bash -c 'getent group cloudflared >/dev/null || groupadd --system cloudflared; id cloudflared >/dev/null 2>&1 || useradd --system --gid cloudflared --no-create-home --home-dir /nonexistent --shell /usr/sbin/nologin cloudflared; install -d -o root -g cloudflared -m 0750 /etc/cloudflared'
pct push 710 "$TASK/rumah-tunnel.json" "/etc/cloudflared/$UUID.json" --perms 0640
cat > "$TASK/rumah-cloudflared.yml" <<CONFIG
tunnel: $UUID
credentials-file: /etc/cloudflared/$UUID.json
protocol: auto
metrics: 127.0.0.1:20241
ingress:
  - hostname: rumah.shizuku.rest
    service: http://127.0.0.1:80
  - service: http_status:404
CONFIG
pct push 710 "$TASK/rumah-cloudflared.yml" /etc/cloudflared/config.yml --perms 0640
pct exec 710 -- chown -R root:cloudflared /etc/cloudflared
cat > "$TASK/rumah-cloudflared.service" <<'SERVICE'
[Unit]
Description=Rumah Cloudflare Tunnel
After=network-online.target nginx.service
Wants=network-online.target

[Service]
Type=simple
User=cloudflared
Group=cloudflared
ExecStart=/usr/local/bin/cloudflared --no-autoupdate --config /etc/cloudflared/config.yml tunnel run
Restart=on-failure
RestartSec=5
TimeoutStopSec=30
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
RestrictAddressFamilies=AF_INET AF_INET6 AF_UNIX

[Install]
WantedBy=multi-user.target
SERVICE
pct push 710 "$TASK/rumah-cloudflared.service" /etc/systemd/system/cloudflared.service --perms 0644
pct exec 710 -- /usr/local/bin/cloudflared --config /etc/cloudflared/config.yml tunnel ingress validate
pct exec 710 -- systemctl daemon-reload
pct exec 710 -- systemctl enable --now cloudflared
pct exec 700 -- cloudflared tunnel route dns "$UUID" rumah.shizuku.rest
printf 'Created dedicated Rumah tunnel %s\n' "$UUID"
date -Is > "$TASK/tunnel-created.done"
