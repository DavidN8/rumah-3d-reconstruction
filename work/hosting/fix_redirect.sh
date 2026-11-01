set -euo pipefail
TASK=/var/lib/vz/rumah-deploy/20261027
cp "$TASK/rumah.nginx" "$TASK/rumah.nginx.before-https-fix"
python3 - "$TASK/rumah.nginx" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1]);s=p.read_text();assert s.count('    server_tokens off;')==1
s=s.replace('    server_tokens off;', '    server_tokens off;\n    absolute_redirect off;')
p.write_text(s)
PY
pct push 710 "$TASK/rumah.nginx" /etc/nginx/sites-available/rumah --perms 0644
pct exec 710 -- nginx -t
pct exec 710 -- systemctl reload nginx
pct exec 710 -- curl -fsS -I http://127.0.0.1/models/iphone-full-room.glb
