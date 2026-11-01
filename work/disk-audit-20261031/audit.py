"""Read-only file metadata audit. Never reads file contents or follows junctions."""
import ctypes
from ctypes import wintypes
from collections import defaultdict
import heapq
import json
import os
from pathlib import Path
import shutil
import time

TASK = Path(__file__).resolve().parents[2]
ROOTS = [
    ('Current Codex task', TASK),
    ('Ruang Kamare source and reconstruction', Path(r'C:\Users\bombe\OneDrive\Documents\ChatGPT\Ruang Kamare')),
    ('Shared Hugging Face cache', Path(r'C:\Users\bombe\.cache\huggingface')),
    ('Shared PyTorch cache', Path(r'C:\Users\bombe\.cache\torch')),
    ('Shared Paddle cache', Path(r'C:\Users\bombe\.cache\paddle')),
]
kernel = ctypes.WinDLL('kernel32', use_last_error=True)
compressed_size = kernel.GetCompressedFileSizeW
compressed_size.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(wintypes.DWORD)]
compressed_size.restype = wintypes.DWORD
seen = {}
results = []
started = time.monotonic()
last_progress = started
for label, root in ROOTS:
    groups = defaultdict(lambda: {'files': 0, 'logical': 0, 'allocated_unique': 0, 'allocated_references': 0})
    totals = {'files': 0, 'logical': 0, 'allocated_unique': 0, 'allocated_references': 0, 'hardlink_references': 0, 'allocation_errors': 0, 'cloud_or_offline_files': 0}
    largest = []
    errors = []
    skips = []
    if not root.exists():
        results.append({'label': label, 'root': str(root), 'missing': True})
        continue
    pending = [root]
    while pending:
        directory = pending.pop()
        try:
            with os.scandir(directory) as entries:
                for entry in entries:
                    try:
                        info = entry.stat(follow_symlinks=False)
                        tag = getattr(info, 'st_reparse_tag', 0)
                        if tag in (0xA0000003, 0xA000000C):
                            skips.append(entry.path)
                            continue
                        if entry.is_dir(follow_symlinks=False):
                            pending.append(Path(entry.path))
                            continue
                        if not entry.is_file(follow_symlinks=False):
                            continue
                        if not info.st_ino:
                            info = os.stat(entry.path, follow_symlinks=False)
                        key = (info.st_dev, info.st_ino) if info.st_ino else entry.path
                        first = key not in seen
                        if first:
                            upper = wintypes.DWORD()
                            ctypes.set_last_error(0)
                            lower = compressed_size(entry.path, ctypes.byref(upper))
                            error = ctypes.get_last_error()
                            if lower == 0xFFFFFFFF and error:
                                allocated = None
                                totals['allocation_errors'] += 1
                                errors.append({'path': entry.path, 'winerror': error})
                            else:
                                allocated = (upper.value << 32) | lower
                            seen[key] = allocated
                        else:
                            allocated = seen[key]
                            totals['hardlink_references'] += 1
                        allocated = allocated or 0
                        rel = Path(entry.path).relative_to(root)
                        totals['files'] += 1
                        totals['logical'] += info.st_size
                        totals['allocated_references'] += allocated
                        totals['allocated_unique'] += allocated if first else 0
                        attrs = getattr(info, 'st_file_attributes', 0)
                        totals['cloud_or_offline_files'] += int(bool(attrs & (0x1000 | 0x40000 | 0x400000)))
                        for depth in range(1, min(4, len(rel.parts) - 1) + 1):
                            group = groups['/'.join(rel.parts[:depth])]
                            group['files'] += 1
                            group['logical'] += info.st_size
                            group['allocated_references'] += allocated
                            group['allocated_unique'] += allocated if first else 0
                        if len(rel.parts) == 1:
                            group = groups['(root files)']
                            group['files'] += 1
                            group['logical'] += info.st_size
                            group['allocated_references'] += allocated
                            group['allocated_unique'] += allocated if first else 0
                        item = (allocated, info.st_size, str(rel))
                        if len(largest) < 50:
                            heapq.heappush(largest, item)
                        elif item > largest[0]:
                            heapq.heapreplace(largest, item)
                    except OSError as exc:
                        errors.append({'path': entry.path, 'error': str(exc)})
            if time.monotonic() - last_progress > 10:
                print(json.dumps({'progress': label, 'files': totals['files'], 'allocated_GiB': round(totals['allocated_unique'] / 2**30, 2)}), flush=True)
                last_progress = time.monotonic()
        except OSError as exc:
            errors.append({'path': str(directory), 'error': str(exc)})
    result = {'label': label, 'root': str(root), **totals, 'groups': dict(groups),
              'largest': [{'allocated': a, 'logical': s, 'path': p} for a, s, p in sorted(largest, reverse=True)],
              'errors': errors, 'skipped_junctions_or_symlinks': skips}
    results.append(result)
    print(json.dumps({'completed': label, **totals, 'allocated_GiB': round(totals['allocated_unique'] / 2**30, 3),
                      'errors': len(errors)}), flush=True)
    (Path(__file__).parent / 'audit.json').write_text(json.dumps({'roots': results}, indent=2), encoding='utf-8')
disk = shutil.disk_usage('C:\\')
report = {'date': '2026-10-31', 'method': 'Metadata only. Windows allocated bytes, with hardlinks counted once across all audited roots. Junctions/symlinks not followed. File content never read.',
          'disk': {'total': disk.total, 'used': disk.used, 'free': disk.free},
          'elapsed_seconds': time.monotonic() - started, 'roots': results}
(Path(__file__).parent / 'audit.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps({'done': True, 'elapsed_seconds': round(report['elapsed_seconds'], 2), 'free_GiB': round(disk.free / 2**30, 2)}), flush=True)
