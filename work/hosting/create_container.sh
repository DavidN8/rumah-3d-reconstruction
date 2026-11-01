set -euo pipefail
TASK=/var/lib/vz/rumah-deploy/20261027
if pct status 710 >/dev/null 2>&1; then echo 'CT710 already exists; no duplicate creation attempted'; exit 0; fi
cat > "$TASK/create-container.sh" <<'SCRIPT'
set -euo pipefail
if pct status 710 >/dev/null 2>&1; then exit 2; fi
pct create 710 local:vztmpl/debian-13-standard_13.1-2_amd64.tar.zst --hostname rumah --unprivileged 1 --cores 2 --memory 2048 --swap 512 --rootfs local-lvm:16 --net0 name=eth0,bridge=vmbr0,ip=dhcp,type=veth --nameserver 1.1.1.1 --onboot 1 --tags 'web;rumah' --description 'Public full native iPhone room viewer at rumah.shizuku.rest. Dedicated unprivileged LXC; no application authentication.'
pct start 710
date -Is > /var/lib/vz/rumah-deploy/20261027/container-created.done
SCRIPT
nohup bash "$TASK/create-container.sh" > "$TASK/create-container.log" 2>&1 < /dev/null &
printf 'Container creation started, task PID %s\n' "$!"
