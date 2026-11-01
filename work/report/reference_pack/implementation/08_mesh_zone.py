"""20261027_IPHONE_WIDE Phase 4c: 8K-textured mesh extraction per zone."""
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
SPIRULA = Path(os.environ.get(
    "SPIRULA_EXE",
    "C:/Users/bombe/OneDrive/Documents/ChatGPT/Ruang Kamare/roomscan-reconstruction"
    "/data/20261019_095800/runtime/spirula/bin/spirula.exe"))
LOGS = BASE / "analysis" / "logs"

for pacing_var in ("SS_GPU_DUTY_CYCLE", "GPU_DUTY_CYCLE", "CUDA_VISIBLE_DEVICES"):
    os.environ.pop(pacing_var, None)
os.environ["OMP_NUM_THREADS"] = str(os.cpu_count() or 12)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--zone", choices=["zone-0", "zone-1", "zone-2"], required=True)
    p.add_argument("--carve-k", type=int, default=3)
    p.add_argument("--iso", type=float, default=0.68)
    p.add_argument("--merge-factor", type=float, default=1.2)
    p.add_argument("--max-grid-res", type=int, default=384)
    p.add_argument("--texture-size", type=int, default=8192)
    p.add_argument("--variant", default="optimized-m12")
    args = p.parse_args()

    ckpt = BASE / "training" / args.zone
    # Never overwrite the trained, full-resolution reference export.
    if not args.variant.replace("-", "").isalnum():
        p.error("variant must contain letters, digits or hyphens")
    dest = BASE / "exports" / args.variant / args.zone
    dest.mkdir(parents=True, exist_ok=True)
    cmd = [
        str(SPIRULA), "mesh", str(ckpt),
        "--data", str(BASE / "zones" / args.zone),
        "--output", str(dest / args.zone),
        "--format", "glb+jpeg90", "--color", "texture",
        "--texture-size", str(args.texture_size),
        "--num-threads", str(os.cpu_count() or 12),
        "--merge-factor", str(args.merge_factor), "--bisection-iters", "4",
        "--max-grid-res", str(args.max_grid_res),
        "--floater-min-faces", "50",
        "--fill-hole-ratio", "0", "--fill-hole-max-edges", "64",
        "--carve-k", str(args.carve_k), "--iso", str(args.iso),
        "--device", "auto",
    ]
    LOGS.mkdir(parents=True, exist_ok=True)
    print("cmd:", " ".join(cmd), flush=True)
    t0 = time.monotonic()
    with (LOGS / f"{args.zone}-mesh-{args.variant}.log").open("wb", buffering=0) as log:
        r = subprocess.run(list(map(str, cmd)), stdout=log, stderr=subprocess.STDOUT,
                           cwd=str(BASE))
    record = {"command": cmd, "exit_code": r.returncode,
              "elapsed_seconds": time.monotonic() - t0}
    (LOGS / f"{args.zone}-mesh-{args.variant}.json").write_text(json.dumps(record, indent=2))
    print(f"mesh {args.zone} exit={r.returncode} "
          f"elapsed={record['elapsed_seconds']:.0f}s", flush=True)
    return r.returncode


if __name__ == "__main__":
    sys.exit(main())
