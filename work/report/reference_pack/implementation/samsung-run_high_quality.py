"""Recorded local Spirula jobs; each room keeps its own source assets."""
import argparse
import datetime
import json
import subprocess
import time
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument('room', choices=['bedroom', 'bathroom'])
p.add_argument('stage', choices=['normals', 'train', 'mesh'])
a = p.parse_args()
root = Path(__file__).resolve().parents[1]
hq = root / 'high-quality'
data = hq / a.room
logs = hq / 'logs'
logs.mkdir(exist_ok=True)
exe = root / 'runtime/spirula/bin/spirula.exe'
if a.stage == 'normals':
    command = [exe, 'geometry', data, '--model', root / 'runtime/spirula/models/moge2-vitl-normal.onnx',
               '--max-size', '1064', '--num-tokens', '3600', '--normal-format', 'png']
elif a.stage == 'train':
    command = [exe, 'train', 'meshing', '--data', data,
               '--output-dir-prefix', hq / 'training', '--output-dir-name', a.room,
               '--quality', 'high', '--cap-max', '3000000' if a.room == 'bedroom' else '2000000',
               '--num-iterations', '50000', '--train-resolution-divisor', '1',
               '--progressive-resolution', '1', '--progressive-resolution-full-at', '0.3',
               '--sh-degree', '3', '--sh-reg', '0.001',
               '--distraction-robustness', 'mild',
               '--steps-per-save', '5000', '--save-only-latest-checkpoint', '0',
               '--save-full-checkpoint', '1', '--eval-mode', 'interval', '--eval-interval', '12',
               '--save-eval-images', '1', '--disable-viewer', '1', '--keep-viewer-alive', '0',
               '--scene-center', 'none', '--train-frame', 'points']
else:
    selection=json.loads((hq/'selection.json').read_text()) if (hq/'selection.json').exists() else {}
    selected=selection.get(a.room,{})
    dest = hq / selected.get('export_dir','exports/'+a.room)
    dest.mkdir(parents=True, exist_ok=True)
    command = [exe, 'mesh', hq / selected.get('training','training/'+a.room), '--data', hq/selected.get('data',a.room),
               '--output', dest / a.room, '--format', 'obj,glb,ply', '--color', 'texture,vertex',
               '--texture-size', '8192', '--num-threads', '12', '--merge-factor', '0.5',
               '--bisection-iters', '4', '--floater-min-faces', '50', '--fill-hole-ratio', '0',
               '--fill-hole-max-edges', str(selected.get('hole_max_edges',8)),
               '--carve-k', str(selected.get('carve_k',1))]
command = list(map(str, command))
record_path = logs / f'{a.room}-{a.stage}.json'
if record_path.exists() and a.stage == 'train':
    previous = json.loads(record_path.read_text())
    if previous['status'] != 'failed' or (hq / 'training' / a.room).exists():
        raise SystemExit('Training record already exists; inspect checkpoint before resuming.')
    suffix = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    record_path.rename(logs / f'{a.room}-{a.stage}-failed-{suffix}.json')
    (logs / f'{a.room}-{a.stage}.log').rename(logs / f'{a.room}-{a.stage}-failed-{suffix}.log')
record = {'command': command, 'started_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
          'status': 'running', 'room': a.room, 'stage': a.stage}
record_path.write_text(json.dumps(record, indent=2))
start = time.monotonic()
print(f'Starting {a.room} {a.stage}', flush=True)
with (logs / f'{a.room}-{a.stage}.log').open('wb', buffering=0) as log:
    result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, cwd=hq)
record.update(status='complete' if result.returncode == 0 else 'failed',
              exit_code=result.returncode, elapsed_seconds=time.monotonic()-start,
              finished_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
record_path.write_text(json.dumps(record, indent=2))
print(json.dumps(record, indent=2), flush=True)
raise SystemExit(result.returncode)
