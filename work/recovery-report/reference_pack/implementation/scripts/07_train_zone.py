"""20261027_IPHONE_WIDE Phase 4b: per-zone GPU training (spirula train meshing).

Follows the proven 20261019_095800 recipe with the mandated settings, plus
frame-preservation flags so every zone trains in the exact same rigid COLMAP
world frame (no per-zone rotation/centering/rescaling). GPU pacing stays OFF.

--max-world-size is calibrated from the solved model: units-per-metre is
estimated from the median camera height above the ground-levelled plane
(handheld phone ~1.5 m), so 0.12 m becomes the equivalent world-unit value.
"""
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from colmap_io import read_model, qvec_to_rotmat  # noqa: E402

BASE = Path(__file__).resolve().parents[1]
SPIRULA = Path(os.environ.get(
    "SPIRULA_EXE",
    "C:/Users/bombe/OneDrive/Documents/ChatGPT/Ruang Kamare/roomscan-reconstruction"
    "/data/20261019_095800/runtime/spirula/bin/spirula.exe"))
LOGS = BASE / "analysis" / "logs"
CAMERA_HEIGHT_M = 1.5

for pacing_var in ("SS_GPU_DUTY_CYCLE", "GPU_DUTY_CYCLE", "CUDA_VISIBLE_DEVICES"):
    os.environ.pop(pacing_var, None)
os.environ["OMP_NUM_THREADS"] = str(os.cpu_count() or 12)


def estimate_units_per_metre(zone="zone-1") -> float:
    # Native coordinate zero is not the floor. For the kitchen it is close to
    # countertop height. Use the measured per-zone scale, including its join.
    measured = BASE / "analysis" / "fixed-transforms.json"
    if not measured.exists():
        raise RuntimeError("Measure floor planes and solve the export frame first (12_merge_models.py)")
    scale = json.loads(measured.read_text())["zones"][zone]["scale"]
    if not np.isfinite(scale) or scale <= 0:
        raise ValueError("Invalid measured metres per training unit")
    return 1.0 / scale


def main() -> int:
    from pipeline_guard import reject_retired_temporal_pipeline
    reject_retired_temporal_pipeline()
    p = argparse.ArgumentParser()
    p.add_argument("--zone", required=True)
    p.add_argument("--cap-max", type=int, default=2_500_000)
    p.add_argument("--num-iterations", type=int, default=40_000)
    p.add_argument("--refine-stop-iter", type=int, default=30_000)
    args = p.parse_args()

    zone_dir = BASE / "zones" / args.zone
    out_name = args.zone
    upm = estimate_units_per_metre(args.zone)
    max_world = round(0.12 * upm, 5)
    seed = zone_dir / "seed.ply"
    seed_arg = ["--seed-pointcloud", str(seed)] if seed.exists() else []

    cmd = [
        str(SPIRULA), "train", "meshing",
        "--data", str(zone_dir),
        "--output-dir-prefix", str(BASE / "training"),
        "--output-dir-name", out_name,
        "--cap-max", str(args.cap_max),
        "--num-iterations", str(args.num_iterations),
        "--refine-stop-iter", str(args.refine_stop_iter),
        "--train-resolution-divisor", "1",
        "--progressive-resolution", "1",
        "--progressive-resolution-full-at", "0.3",
        "--max-world-size", str(max_world),
        "--sh-degree", "3", "--sh-reg", "0.001",
        "--distraction-robustness", "mild", "--floater-suppression", "mild",
        "--load-depths", "1", "--load-normals", "1",
        "--depth-supervision-weight", "0.05",
        "--normal-supervision-weight", "0.02",
        "--median-normal-supervision-weight", "0.01",
        "--scene-center", "none", "--train-frame", "points",
        "--orientation-method", "none", "--center-method", "none",
        "--auto-scale-poses", "0",
        "--eval-mode", "interval", "--eval-interval", "12",
        "--save-eval-images", "1",
        "--steps-per-save", "5000", "--save-only-latest-checkpoint", "0",
        "--save-full-checkpoint", "1",
        "--disable-viewer", "1", "--keep-viewer-alive", "0",
        "--device", "auto",
    ] + seed_arg

    LOGS.mkdir(parents=True, exist_ok=True)
    record_path = LOGS / f"{out_name}-train.json"
    print("units/metre:", upm, " max-world-size:", max_world, flush=True)
    print("cmd:", " ".join(cmd), flush=True)
    t0 = time.monotonic()
    with (LOGS / f"{out_name}-train.log").open("wb", buffering=0) as log:
        r = subprocess.run(list(map(str, cmd)), stdout=log, stderr=subprocess.STDOUT,
                           cwd=str(BASE))
    record = {"command": cmd, "exit_code": r.returncode,
              "elapsed_seconds": time.monotonic() - t0,
              "units_per_metre": upm, "max_world_size": max_world}
    record_path.write_text(json.dumps(record, indent=2))
    print(f"train {out_name} exit={r.returncode} "
          f"elapsed={record['elapsed_seconds']:.0f}s", flush=True)
    return r.returncode


if __name__ == "__main__":
    sys.exit(main())
