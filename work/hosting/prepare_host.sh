set -euo pipefail
TASK=/var/lib/vz/rumah-deploy/20261027
install -d -m 700 "$TASK"
pct config 700 > "$TASK/frufru-ct700-config-before.txt"
pct exec 700 -- systemctl is-enabled nginx > "$TASK/frufru-nginx-enabled-before.txt"
pct exec 700 -- systemctl is-active cloudflared > "$TASK/frufru-tunnel-state-before.txt"
pct exec 700 -- sh -c 'nginx -T 2>/dev/null' > "$TASK/frufru-nginx-config-before.txt"
pct exec 700 -- systemctl disable --now nginx
pct exec 700 -- systemctl is-active cloudflared
if pct exec 700 -- systemctl is-active --quiet nginx; then echo 'Frufru nginx failed to stop'; exit 1; fi
python3 - <<'PY'
import json,subprocess,datetime
from pathlib import Path
p=Path('/var/lib/vz/rumah-deploy/20261027')
r={'frufru_web_service':'stopped and disabled','container_700':'left running to preserve tracker.shizuku.rest tunnel','files_and_configuration':'preserved','restore':'pct exec 700 -- systemctl enable --now nginx','utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
(p/'frufru-shutdown-receipt.json').write_text(json.dumps(r,indent=2));print(json.dumps(r))
PY
pct exec 700 -- cloudflared tunnel list --output json | python3 -c 'import sys,json;print(json.dumps([{k:x.get(k) for k in ["id","name","createdAt"]} for x in json.load(sys.stdin)],indent=2))'
if pct status 710 >/dev/null 2>&1; then echo 'CT710 already exists; inspect before doing anything else'; exit 2; fi
cat > "$TASK/create-container.sh" <<'SCRIPT'
set -euo pipefail
pct create 710 local:vztmpl/debian-13-standard_13.1-2_amd64.tar.zst --hostname rumah --unprivileged 1 --cores 2 --memory 2048 --swap 512 --rootfs local-lvm:16 --net0 name=eth0,bridge=vmbr0,ip=dhcp,type=veth --nameserver 1.1.1.1 --onboot 1 --tags 'web;rumah' --description 'Public full native iPhone room viewer at rumah.shizuku.rest. Dedicated unprivileged LXC; no application authentication.'
pct start 710
date -Is > /var/lib/vz/rumah-deploy/20261027/container-created.done
SCRIPT
nohup bash "$TASK/create-container.sh" > "$TASK/create-container.log" 2>&1 < /dev/null &
printf 'Container creation started, task PID %s\n' "$!"
