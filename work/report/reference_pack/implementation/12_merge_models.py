"""Rebuild the corrected iPhone merge without changing checkpoint datasets.

The former walking-speed scale and tight-ICP wrong-wall selection are removed.
Raw component models and the original merged frame in backups are immutable.
Fresh metric depth and GPU LoFTR evidence are prepared by stages 14 and 15.
"""
import subprocess
import sys
from pathlib import Path

BASE=Path(__file__).resolve().parents[1]


def main():
    needed=[BASE/'backups/before-fix-20261027/merged/sparse/0/images.txt',
            BASE/'analysis/bridge-dense.npz',BASE/'analysis/metric-scales.json']
    for p in needed:
        if not p.exists():raise RuntimeError(f'Missing preserved input/evidence: {p}. Run metric stages 14/15 after preserving the original frame.')
    for script in ['18_measure_planes.py','16_solve_frame.py','09_merge_export.py']:
        subprocess.run([sys.executable,str(BASE/'scripts'/script)],cwd=BASE,check=True)
    print('Baked upright GLB + 501 consistent cameras exported; original checkpoints unchanged.')
    return 0


if __name__=='__main__':raise SystemExit(main())
