"""20261027_IPHONE_WIDE Gate 2: compose side-by-side QA renders vs source frames.

Inputs: analysis/raytrace-check/renders/*.png (Cycles CPU/Embree renders, RGBA,
540x960, cameras rebuilt from COLMAP poses) and the source keyframes.
Outputs: analysis/raytrace-check/<name>-sbs.jpg pairs, per-view coverage
metrics, and Gaussian splat scale p90 read from the trained checkpoints.
Gate: mean coverage >= 0.88 and scale p90 (world units) <= 0.06.
"""
import json
import struct
import sys
from pathlib import Path

import cv2
import numpy as np

BASE = Path(__file__).resolve().parents[1]
CHECK = BASE / "analysis" / "raytrace-check"
OUT_JSON = BASE / "analysis" / "gate2-visual.json"


def splat_scale_p90(ckpt_dir: Path) -> float | None:
    """p90 of splat world scales (max over the three scale axes)."""
    plys = sorted(ckpt_dir.glob("**/splat.ply"))
    if not plys:
        return None
    path = plys[-1]
    data = path.read_bytes()
    head_end = data.index(b"end_header\n") + len(b"end_header\n")
    head = data[:head_end]
    if b"binary_little_endian" not in head:
        return None
    n = int(head.split(b"element vertex ")[1].split(b"\n")[0])
    props = [l.split() for l in head.splitlines() if l.startswith(b"property")]
    names = [p[2].decode() for p in props]
    sizes = {"float": 4, "double": 8, "uchar": 1}
    itemsize = sum(sizes[p[1].decode()] for p in props)
    if not all(k in names for k in ("scale_0", "scale_1", "scale_2")):
        return None
    arr = np.frombuffer(data[head_end:head_end + n * itemsize],
                        dtype=np.uint8).reshape(n, itemsize)
    flat = arr.view("<f4").reshape(n, len(props)) if itemsize % 4 == 0 else None
    cols = {p[2].decode(): i for i, p in enumerate(props)}
    s = np.stack([flat[:, cols[k]] for k in ("scale_0", "scale_1", "scale_2")], 1)
    # spirula stores raw (pre-activation) log scales; world scale = exp(raw)
    return float(np.percentile(np.exp(s.max(1)), 90))


def main() -> int:
    if (BASE/'colmap-gpu/merged/sparse/0/FRAME.json').exists():
        # The historical coverage-only gate hid holes behind farther surfaces.
        # A corrected export is checked using the actual WebGL screenshots.
        renders=sorted((BASE/'analysis/fixed-renders').glob('*-compare.png'))
        report={'status':'PARTIAL','actual_webgl_comparison_views':len(renders),
                'renders':[str(p.relative_to(BASE)) for p in renders],
                'orientation_and_projection_report':'analysis/fixed-geometry-check.json',
                'control_and_performance_report':'analysis/fixed-controls-check.json',
                'reason':'Upright orientation, controls and size verified. Holes and transient-object surfaces remain in recorded views, especially at the bedroom doorway. Seam alignment is depth-derived, not independently surveyed.'}
        OUT_JSON.write_text(json.dumps(report,indent=2))
        print(json.dumps(report,indent=2))
        return 2
    renders = sorted((CHECK / "renders").glob("*.png"))
    if not renders:
        print("no renders found", file=sys.stderr)
        return 1
    views = []
    for png in renders:
        img = cv2.imread(str(png), cv2.IMREAD_UNCHANGED)
        if img is None:
            continue
        if img.ndim == 2:
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        if img.shape[2] == 4:
            alpha = img[:, :, 3]
            bgr = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
            bg = np.full_like(bgr, (18, 22, 28))
            a = (alpha.astype(np.float32) / 255)[:, :, None]
            bgr = (bgr * a + bg * (1 - a)).astype(np.uint8)
        else:
            alpha = np.full(img.shape[:2], 255, np.uint8)
            bgr = img
        stem = png.stem
        src = None
        for cand in (BASE / "frames").glob(f"{stem}*.jpg"):
            src = cand
            break
        coverage = float((alpha > 127).mean())
        empty = float((alpha < 5).mean())
        if src is not None:
            photo = cv2.imread(str(src))
            photo = cv2.resize(photo, (bgr.shape[1], bgr.shape[0]))
            h = bgr.shape[0]
            sep = np.full((h, 6, 3), 70, np.uint8)
            sbs = np.concatenate([photo, sep, bgr], 1)
            cv2.putText(sbs, "SOURCE", (10, 40), 0, 1.1, (255, 255, 255), 2)
            cv2.putText(sbs, "MESH RENDER (CPU Cycles/Embree)",
                        (bgr.shape[1] + 16, 40), 0, 1.0, (120, 220, 255), 2)
            out = CHECK / f"{stem}-sbs.jpg"
            cv2.imwrite(str(out), sbs, [cv2.IMWRITE_JPEG_QUALITY, 92])
        views.append({"image": stem, "coverage": coverage, "empty": empty})

    scales = {}
    for zdir in sorted((BASE / "training").glob("zone-*")):
        if zdir.is_dir():
            scales[zdir.name] = splat_scale_p90(zdir)

    mean_cov = float(np.mean([v["coverage"] for v in views]))
    max_scale = max((s for s in scales.values() if s is not None), default=None)
    gate = {
        "views": views,
        "mean_coverage": mean_cov,
        "splat_scale_p90_world_units": scales,
        "gate_scale_p90_limit": 0.06,
        "pass": bool(mean_cov >= 0.88 and
                     (max_scale is None or max_scale <= 0.06)),
    }
    OUT_JSON.write_text(json.dumps(gate, indent=1))
    print(json.dumps({k: v for k, v in gate.items() if k != "views"}, indent=1))
    for v in views:
        print(f"  {v['image']}: coverage {v['coverage']:.3f}")
    return 0 if gate["pass"] else 2


if __name__ == "__main__":
    sys.exit(main())
