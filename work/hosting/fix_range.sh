set -euo pipefail
TASK=/var/lib/vz/rumah-deploy/20261027
cp "$TASK/rumah.nginx" "$TASK/rumah.nginx.before-range-fix"
python3 - "$TASK/rumah.nginx" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1]);s=p.read_text();marker='    location ~ \\.glb$ {'
assert s.count(marker)==1 and '@native_range' not in s
s=s.replace(marker,marker+'\n        error_page 418 = @native_range;\n        if ($http_range != "") { return 418; }')
s=s.replace('        add_header Vary Accept-Encoding;\n','')
s=s.replace('    location ~ /\\. { deny all; }','''    location @native_range {
        types { }
        default_type model/gltf-binary;
        gzip off;
        gzip_static off;
        add_header Cache-Control "public, max-age=31536000, immutable";
        add_header X-Content-Type-Options nosniff always;
        add_header X-Robots-Tag "noindex, nofollow" always;
        try_files $uri =404;
    }
    location ~ /\\. { deny all; }''')
p.write_text(s)
PY
pct push 710 "$TASK/rumah.nginx" /etc/nginx/sites-available/rumah --perms 0644
pct exec 710 -- nginx -t
pct exec 710 -- systemctl reload nginx
pct exec 710 -- curl -fsS -I -H 'Range: bytes=0-11' -H 'Accept-Encoding: gzip' http://127.0.0.1/models/iphone-full-room-16f8963b.glb
