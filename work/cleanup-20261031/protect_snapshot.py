"""Metadata fingerprints of the iPhone work and its shared runtime; no removals."""
from pathlib import Path
import hashlib
import json
import os
import shutil
import sys

HERE = Path(__file__).parent
TASK = HERE.parents[1]
PROJECT = Path(r'C:\Users\bombe\OneDrive\Documents\ChatGPT\Ruang Kamare')
ROOTS = {
    'iphone': PROJECT / 'roomscan-reconstruction/data/20261027_IPHONE_WIDE',
    'shared_runtime': PROJECT / 'roomscan-reconstruction/data/20261019_095800/runtime',
    'delivered_outputs': TASK / 'outputs',
    'phone_viewer_source': TASK / 'work/mobile-20261029',
}

def snapshot(root):
    rows = {}
    for directory, folders, files in os.walk(root, followlinks=False):
        for name in files:
            path = Path(directory) / name
            info = os.stat(path, follow_symlinks=False)
            rows[str(path.relative_to(root))] = [info.st_size, info.st_mtime_ns, info.st_ino]
    encoded = json.dumps(rows, sort_keys=True, separators=(',', ':')).encode()
    return {'path': str(root), 'file_count': len(rows),
            'logical_bytes': sum(row[0] for row in rows.values()),
            'metadata_sha256': hashlib.sha256(encoded).hexdigest(), 'files': rows}

def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda: source.read(8 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()

mode = sys.argv[1]
assert mode in ('before', 'after')
result = {'date': '2026-10-31', 'disk_free': shutil.disk_usage('C:\\').free,
          'protected': {name: snapshot(root) for name, root in ROOTS.items()},
          'native_sha256': sha(TASK / 'outputs/iPhone_Wide_Full_Native.glb'),
          'phone_sha256': sha(TASK / 'work/mobile-20261029/public/models/iphone-phone-2b811d1241.glb')}
if mode == 'after':
    prior = json.loads((HERE / 'protected-before.json').read_text())
    result['unchanged'] = {}
    for name, data in result['protected'].items():
        before = prior['protected'][name]
        result['unchanged'][name] = data['metadata_sha256'] == before['metadata_sha256']
        if not result['unchanged'][name]:
            result.setdefault('differences', {})[name] = {
                'added': sorted(set(data['files']) - set(before['files'])),
                'removed': sorted(set(before['files']) - set(data['files'])),
                'changed': sorted(k for k in data['files'].keys() & before['files'].keys()
                                  if data['files'][k] != before['files'][k]),
            }
    result['model_hashes_unchanged'] = all(result[k] == prior[k] for k in ('native_sha256', 'phone_sha256'))
    result['disk_free_change'] = result['disk_free'] - prior['disk_free']
(HERE / f'protected-{mode}.json').write_text(json.dumps(result, indent=2))
print(json.dumps({k: v for k, v in result.items() if k != 'protected'}, indent=2))
print(json.dumps({name: {k: v for k, v in data.items() if k != 'files'}
                  for name, data in result['protected'].items()}, indent=2))
if mode == 'after':
    assert all(result['unchanged'].values()) and result['model_hashes_unchanged'], 'Protected files changed; inspect differences.'
