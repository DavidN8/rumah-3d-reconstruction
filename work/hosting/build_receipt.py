import os
from pathlib import Path
import hashlib, json, struct, datetime
w = Path(__file__).parent
root = w.parent.parent
model = w / 'public-model-verified.glb'
expected = '16f8963b043a766317497ee4281f4cf39c6b2190fafaaed51334734723c8b207'
h = hashlib.sha256()
with model.open('rb') as f:
    for block in iter(lambda: f.read(8 * 1024 * 1024), b''):
        h.update(block)
assert h.hexdigest() == expected
with model.open('rb') as f:
    magic, version, length = struct.unpack('<4sII', f.read(12))
    chunk_len, chunk_type = struct.unpack('<I4s', f.read(8))
    gltf = json.loads(f.read(chunk_len))
assert magic == b'glTF' and version == 2 and (length == 435614584)
triangles = sum((gltf['accessors'][p['indices']]['count'] // 3 for m in gltf['meshes'] for p in m['primitives'] if p.get('mode', 4) == 4))
assert triangles == 11891853
evidence = {'site': 'https://rumah.shizuku.rest/', 'captured_at': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'authentication_required': False, 'lxc': {'id': 710, 'hostname': 'rumah', 'distribution': 'Debian 13', 'unprivileged': True, 'cores': 2, 'memory_mib': 2048, 'disk_gib': 16, 'onboot': True}, 'native_model': {'bytes': length, 'triangles': triangles, 'sha256': expected, 'downloaded_through_public_https': True, 'lossless_gzip_transfer_bytes': 302564257, 'transfer_seconds': 38.789415}, 'public_download_verification_note': 'Desktop DNS held a cached NXDOMAIN. The full HTTPS download and range check used the public Cloudflare address resolved independently by the Proxmox host; normal TLS hostname verification remained enabled.', 'range_verification': {'status': 206, 'bytes': 12, 'total_bytes': 435614584, 'body_hex': (w / 'public-range.bin').read_bytes().hex()}, 'services': ['nginx', 'cloudflared 2026.10.4'], 'reboot_verified': True, 'reference_photos': 8, 'frufru': {'nginx': 'stopped and disabled', 'container_700': 'kept running because its tunnel also routes tracker.shizuku.rest', 'shared_cloudflared': 'running', 'tracker_backend': 'CONFIGURED_OUT_OF_BAND:8090 was unreachable; left unchanged'}, 'internal_reports_published': False, 'browser_verification': 'pending desktop DNS refresh', 'initial_backup': 'pending completion'}
out = root / 'outputs'
out.mkdir(exist_ok=True)
(w / 'deployment-evidence.json').write_text(json.dumps(evidence, indent=2), encoding='utf-8')
print(json.dumps({'native_sha256': h.hexdigest(), 'triangles': triangles, 'range_body_verified': evidence['range_verification']['body_hex'] == '676c54460200000078f3f619'}))
