from pathlib import Path
import json

HERE = Path(__file__).parent
TASK = HERE.parents[1]
plan = json.loads((HERE / 'deletion-plan.json').read_text(encoding='utf-8-sig'))
journal = [json.loads(line) for line in (HERE / 'deletion-journal.jsonl').read_text(encoding='utf-8-sig').splitlines()]
verified = json.loads((HERE / 'protected-after.json').read_text())
after_audit = json.loads((TASK / 'work/disk-audit-20261031/audit.json').read_text())
completion = journal[-1]
assert completion['event'] == 'complete' and completion['removedTargets'] == 25
assert all(verified['unchanged'].values()) and verified['model_hashes_unchanged']
assert not any(Path(target['path']).exists() for target in plan['targets'])
gib = lambda n: n / 2**30
summary = {
    'date': '2026-10-31', 'status': 'complete',
    'physical_free_space_before_bytes': completion['freeBytesBefore'],
    'physical_free_space_after_bytes': completion['freeBytesAfter'],
    'physical_free_space_gain_bytes': completion['freeBytesChange'],
    'removed': plan['targets'],
    'kept_shared_runtime_reason': plan['sharedRuntimeReason'],
    'protected_file_checks': {name: {k: v for k, v in data.items() if k != 'files'}
                             for name, data in verified['protected'].items()},
    'protected_metadata_unchanged': verified['unchanged'],
    'native_model_sha256': verified['native_sha256'],
    'phone_model_sha256': verified['phone_sha256'],
    'shared_ai_caches_unchanged': True,
    'live_viewer_manifest': json.loads((HERE / 'live-manifest.json').read_text())['build'],
    'remaining_project_file_data_bytes': after_audit['roots'][1]['allocated_unique'],
    'note': 'Space units in the text receipt match Windows Explorer (GiB displayed as GB). The free-space gain is the measured volume change, not the sum of file names. Protection checks ran before creating these two new receipt files.',
}
out = TASK / 'outputs'
(out / 'Storage_Cleanup_2026-10-31.json').write_text(json.dumps(summary, indent=2))
lines = [
    'Room reconstruction storage cleanup — 31 October 2026', '',
    'Completed at the user\'s request: retire Nikon and Samsung; retain iPhone.', '',
    f'Measured C: space freed: {gib(completion["freeBytesChange"]):.2f} GB',
    f'C: free space before: {gib(completion["freeBytesBefore"]):.2f} GB',
    f'C: free space after: {gib(completion["freeBytesAfter"]):.2f} GB',
    'Units match Windows Explorer. This is actual volume free-space change.', '',
    'Removed:',
    '- Nikon project capture, datasets, processing runs, training and exports.',
    '- Samsung footage, processing runs, training and exports.',
    '- Five retired Samsung release/test-copy folders and the prepared',
    '  high-quality viewer cache, together approximately 9.6 GB.', '',
    'Retained:',
    '- All 21,324 iPhone files. Metadata fingerprint identical before/after.',
    '- All existing delivered reports, models, images and offline viewer.',
    '- Phone viewer source and assets. Metadata fingerprint identical.',
    '- Approximately 17.7 GB of shared reconstruction tools at the existing',
    '  Samsung runtime path. Current iPhone scripts call Spirula and Python',
    '  from that directory. Keeping its path avoids breaking iPhone rebuilds.',
    '- Project source code, documentation and small model catalogs.',
    '- Shared Hugging Face / PyTorch caches, used by other work.', '',
    'Both delivered model SHA256 hashes are unchanged:',
    'Native: ' + verified['native_sha256'],
    'Phone:  ' + verified['phone_sha256'], '',
    'The live rumah viewer was not redeployed or changed. Its public manifest',
    'remained reachable and identifies release 20261029-fullheight-v1.', '',
    'Shared runtime kept:', plan['protected'][1], '',
    'Exact removal list (all 25 paths verified absent):',
]
lines.extend(target['path'] for target in plan['targets'])
(out / 'Storage_Cleanup_2026-10-31.txt').write_text('\n'.join(lines) + '\n', encoding='utf-8')
print(json.dumps({'status': 'complete', 'freed_GiB': round(gib(completion['freeBytesChange']), 2),
                  'free_after_GiB': round(gib(completion['freeBytesAfter']), 2),
                  'protected_unchanged': verified['unchanged'],
                  'receipts': ['Storage_Cleanup_2026-10-31.txt', 'Storage_Cleanup_2026-10-31.json']}, indent=2))
