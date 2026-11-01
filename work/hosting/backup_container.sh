set -euo pipefail
TASK=/var/lib/vz/rumah-deploy/20261027
test -f "$TASK/connector-updated.done"
cat > "$TASK/backup-container.sh" <<'SCRIPT'
set -euo pipefail
TASK=/var/lib/vz/rumah-deploy/20261027
nice -n 10 vzdump 710 --mode snapshot --storage local --compress zstd --remove 0 --bwlimit 20480 --quiet 1
BACKUP=$(find /var/lib/vz/dump -maxdepth 1 -name 'vzdump-lxc-710-*.tar.zst' -type f -printf '%T@ %p\n' | sort -rn | head -1 | cut -d' ' -f2-)
test -n "$BACKUP"
chmod 640 "$BACKUP"
sha256sum "$BACKUP" > "$TASK/initial-backup.sha256"
stat -c 'Backup %n, %s bytes, mode %a' "$BACKUP"
date -Is > "$TASK/initial-backup.done"
SCRIPT
nohup bash "$TASK/backup-container.sh" > "$TASK/backup-container.log" 2>&1 < /dev/null &
printf 'Own container backup process %s\n' "$!"
