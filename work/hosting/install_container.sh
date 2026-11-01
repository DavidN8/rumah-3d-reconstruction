set -euo pipefail
TASK=/var/lib/vz/rumah-deploy/20261027
test -f "$TASK/container-created.done"
pct exec 710 -- ip -brief -4 address show eth0
cat > "$TASK/install-container.sh" <<'SCRIPT'
set -euo pipefail
pct exec 710 -- env DEBIAN_FRONTEND=noninteractive LC_ALL=C.UTF-8 bash -c 'apt-get update && apt-get -y upgrade && apt-get install -y nginx ca-certificates curl && systemctl enable nginx'
date -Is > /var/lib/vz/rumah-deploy/20261027/container-installed.done
SCRIPT
nohup bash "$TASK/install-container.sh" > "$TASK/install-container.log" 2>&1 < /dev/null &
printf 'Software installation task PID %s\n' "$!"
