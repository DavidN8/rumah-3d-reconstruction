set -euo pipefail
python3 - <<'PY'
import pathlib,json,subprocess
p=pathlib.Path('/var/lib/vz/rumah-deploy/20261027')
out={'assets':json.loads((p/'public-assets-verified.json').read_text())}
out['backup_complete']=(p/'initial-backup.done').exists()
if out['backup_complete']:
    out['backup_sha256_record']=(p/'initial-backup.sha256').read_text().strip()
    out['backup_completed_at']=(p/'initial-backup.done').read_text().strip()
out['backup_log_tail']='\n'.join((p/'backup-container.log').read_text().splitlines()[-5:])
out['connector_ready']=json.loads(subprocess.check_output(['pct','exec','710','--','curl','-fsS','--max-time','5','http://127.0.0.1:20241/ready']))
out['native_server_sha256']=subprocess.check_output(['pct','exec','710','--','sha256sum','/var/www/rumah/current/models/iphone-full-room-16f8963b.glb']).decode().split()[0]
print(json.dumps(out,indent=2))
PY
