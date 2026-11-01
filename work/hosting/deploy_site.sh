set -euo pipefail
TASK=/var/lib/vz/rumah-deploy/20261027
echo '55e0b25dc437ce4474c2079e46d303d5ad6e790afe0cd4cac3e053a09007db48  /var/lib/vz/rumah-deploy/20261027/site.tar.partial' | sha256sum -c -
mv "$TASK/site.tar.partial" "$TASK/site.tar"
RELEASE=/var/www/rumah/releases/20261027-full-native
pct exec 710 -- mkdir -p "$RELEASE"
pct exec 710 -- tar -xf - -C "$RELEASE" < "$TASK/site.tar"
pct exec 710 -- bash -c 'set -euo pipefail; cd /var/www/rumah/releases/20261027-full-native/models; gzip -dc iphone-full-room-16f8963b.glb.gz > iphone-full-room-16f8963b.glb.partial; echo "16f8963b043a766317497ee4281f4cf39c6b2190fafaaed51334734723c8b207  iphone-full-room-16f8963b.glb.partial" | sha256sum -c -; mv iphone-full-room-16f8963b.glb.partial iphone-full-room-16f8963b.glb'
cat > "$TASK/rumah.nginx" <<'CONFIG'
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name rumah.shizuku.rest;
    root /var/www/rumah/current;
    index index.html;
    autoindex off;
    server_tokens off;
    absolute_redirect off;
    sendfile on;
    gzip_vary on;
    add_header X-Content-Type-Options nosniff always;
    add_header Referrer-Policy strict-origin-when-cross-origin always;
    add_header X-Robots-Tag "noindex, nofollow" always;
    location = /models/iphone-full-room.glb {
        add_header Cache-Control "no-store";
        return 307 /models/iphone-full-room-16f8963b.glb;
    }
    location ~ \.glb$ {
        error_page 418 = @native_range;
        if ($http_range != "") { return 418; }
        types { }
        default_type model/gltf-binary;
        gzip_static on;
        add_header Cache-Control "public, max-age=31536000, immutable";
        add_header X-Content-Type-Options nosniff always;
        add_header X-Robots-Tag "noindex, nofollow" always;
        try_files $uri =404;
    }
    location @native_range {
        types { }
        default_type model/gltf-binary;
        gzip off;
        gzip_static off;
        add_header Cache-Control "public, max-age=31536000, immutable";
        add_header X-Content-Type-Options nosniff always;
        add_header X-Robots-Tag "noindex, nofollow" always;
        try_files $uri =404;
    }
    location ~ /\. { deny all; }
    location / {
        add_header Cache-Control "no-cache";
        add_header X-Content-Type-Options nosniff always;
        add_header X-Robots-Tag "noindex, nofollow" always;
        try_files $uri $uri/ =404;
    }
}
CONFIG
pct push 710 "$TASK/rumah.nginx" /etc/nginx/sites-available/rumah --perms 0644
pct exec 710 -- bash -c 'set -euo pipefail; ln -sfn /var/www/rumah/releases/20261027-full-native /var/www/rumah/current; if test -L /etc/nginx/sites-enabled/default; then unlink /etc/nginx/sites-enabled/default; fi; ln -sfn /etc/nginx/sites-available/rumah /etc/nginx/sites-enabled/rumah; nginx -t; systemctl enable --now nginx; systemctl reload nginx'
pct exec 710 -- curl -fsS -I http://127.0.0.1/
pct exec 710 -- curl -fsS -I -H 'Accept-Encoding: gzip' http://127.0.0.1/models/iphone-full-room-16f8963b.glb
pct exec 710 -- bash -c 'curl -fsS -H "Accept-Encoding: identity" --range 0-11 http://127.0.0.1/models/iphone-full-room-16f8963b.glb | od -An -tx1'
date -Is > "$TASK/site-deployed.done"
