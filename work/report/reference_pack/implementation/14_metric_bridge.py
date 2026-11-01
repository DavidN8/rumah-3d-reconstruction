"""Recompute metric MoGe depth without overwriting training's relative PNGs."""
import json
import os
from pathlib import Path
import subprocess
import shutil
import numpy as np
from colmap_io import read_model

BASE = Path(__file__).resolve().parents[1]
SPIRULA = BASE.parent / "20261019_095800/runtime/spirula/bin/spirula.exe"


def main():
    os.environ["OMP_NUM_THREADS"] = str(max(12, os.cpu_count() or 12))
    for key in ("SS_GPU_DUTY_CYCLE", "GPU_DUTY_CYCLE", "CUDA_VISIBLE_DEVICES"):
        os.environ.pop(key, None)
    ds = BASE / "analysis/metric-bridge"
    (ds / "images").mkdir(parents=True, exist_ok=True)
    (ds / "sparse/0").mkdir(parents=True, exist_ok=True)
    rows, camera_rows = [], []
    for z in (0, 1):
        cams, images, _ = read_model(BASE / f"colmap-gpu/ws/sparse/{z}")
        cam = next(iter(cams.values()))
        camera_rows.append(f"{z+1} {cam['model']} {cam['width']} {cam['height']} " + " ".join(map(str, cam['params'])))
        values = sorted(images.values(), key=lambda x: x["name"])
        selected = values[-24:] if z == 0 else values[:30]
        selected += values[::max(1, len(values)//12)]
        names = set()
        for im in selected:
            if im['name'] in names:
                continue
            names.add(im['name'])
            src, dst = BASE / 'frames' / im['name'], ds / 'images' / im['name']
            if not dst.exists():
                try:
                    os.link(src, dst)
                except OSError:
                    shutil.copy2(src, dst)
            rows.append(f"{len(rows)+1} " + " ".join(map(str, im['qvec'])) + " " +
                        " ".join(map(str, im['tvec'])) + f" {z+1} {im['name']}\n")
    (ds / 'sparse/0/cameras.txt').write_text('\n'.join(camera_rows)+'\n')
    (ds / 'sparse/0/images.txt').write_text('\n'.join(rows)+'\n')
    (ds / 'sparse/0/points3D.txt').write_text('# Empty: only poses needed for geometry inference\n')
    cmd = [str(SPIRULA), 'geometry', str(ds), '--model', str(SPIRULA.parent.parent / 'models/moge2-vitl-normal.onnx'),
           '--depth', '--depth-units', 'mm', '--ray-depth', 'no', '--max-size', '1064',
           '--num-tokens', '3600', '--normal-format', 'png', '--device', 'auto']
    with (BASE / 'analysis/logs/metric-bridge.log').open('wb', buffering=0) as log:
        r = subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT, cwd=BASE)
    (ds / 'provenance.json').write_text(json.dumps({'command': cmd, 'images': len(rows),
                            'depth_units': 'millimetres', 'exit_code': r.returncode}, indent=2))
    print('Metric depth',len(rows),'frames, exit',r.returncode, flush=True)
    return r.returncode


if __name__ == '__main__':
    raise SystemExit(main())
