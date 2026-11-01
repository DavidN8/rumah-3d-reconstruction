"""20261027_IPHONE_WIDE Phase 3: dense seed cloud from MoGe-2 depth maps.

For every registered frame the MoGe depth map is robustly aligned to the solved
COLMAP sparse points with a linear fit z = alpha*d + beta (RANSAC). Grid pixels
of every 4th frame are then backprojected to world coordinates and kept only
when >=3 of 6 neighbouring views agree within 3% depth. Output: a binary PLY
seed cloud (zones/dataset-unified/seed-cloud.ply) so flat walls/floors/counters
start Gaussian Splatting densely seeded.

World/units: identical to the COLMAP model (no normalization anywhere).
"""
import json
import os
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from colmap_io import read_model, qvec_to_rotmat  # noqa: E402

BASE = Path(__file__).resolve().parents[1]
DS = Path(os.environ.get("DATASET_DIR", str(BASE / "zones" / ("dataset-upright" if
    (BASE / "colmap-gpu/merged/sparse/0/FRAME.json").exists() else "dataset-unified"))))
OUT_PLY = Path(os.environ.get('SEED_OUTPUT_PLY',str(DS / "seed-cloud.ply")))
OUT_JSON = Path(os.environ.get('SEED_OUTPUT_JSON',str(BASE / "analysis" / ("seed-cloud-upright.json" if DS.name == "dataset-upright" else "seed-cloud.json"))))

GRID = 4            # backproject every GRID-th pixel in each axis
FRAME_STRIDE = 2    # every 2nd registered frame
MAX_POINTS = int(os.environ.get('SEED_MAX_POINTS','800000'))
VOXEL_DIVISOR = int(os.environ.get('SEED_VOXEL_DIVISOR','300'))
CONSIST_NEIGHBORS = 6
CONSIST_MIN_AGREE = 3
CONSIST_TOL = 0.03


def undistort_points(xn, yn, k1, k2, p1, p2, iters=10):
    """Iteratively invert the OPENCV distortion. xn,yn: normalized coords."""
    xd, yd = xn.copy(), yn.copy()
    for _ in range(iters):
        r2 = xd * xd + yd * yd
        radial = 1 + k1 * r2 + k2 * r2 * r2
        dx = 2 * p1 * xd * yn * 0  # placeholder removed below
        dx = 2 * p1 * xd * yd + p2 * (r2 + 2 * xd * xd)
        dy = p1 * (r2 + 2 * yd * yd) + 2 * p2 * xd * yd
        xd = (xn - dx) / radial
        yd = (yn - dy) / radial
    return xd, yd


def distort_points(xn, yn, k1, k2, p1, p2):
    r2 = xn * xn + yn * yn
    radial = 1 + k1 * r2 + k2 * r2 * r2
    dx = 2 * p1 * xn * yn + p2 * (r2 + 2 * xn * xn)
    dy = p1 * (r2 + 2 * yn * yn) + 2 * p2 * xn * yn
    return xn * radial + dx, yn * radial + dy


def load_depth(path: Path) -> np.ndarray:
    img = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if img is None:
        raise FileNotFoundError(path)
    if img.ndim == 3:
        img = img[:, :, 0]
    return img.astype(np.float64)


def fit_alignment(depth, P_w, R, t, K, dist):
    """RANSAC linear fit z_cam = alpha*d + beta against projected sparse points."""
    k1, k2, p1, p2 = dist
    fx, fy, cx, cy = K
    X_cam = P_w @ R.T + t
    z = X_cam[:, 2]
    ok = z > 0.02
    if ok.sum() < 40:
        return None
    xn, yn = X_cam[ok, 0] / z[ok], X_cam[ok, 1] / z[ok]
    xd, yd = distort_points(xn, yn, k1, k2, p1, p2)
    u = np.round(fx * xd + cx).astype(int)
    v = np.round(fy * yd + cy).astype(int)
    h, w = depth.shape
    inb = (u >= 0) & (u < w) & (v >= 0) & (v < h)
    if inb.sum() < 40:
        return None
    d = depth[v[inb], u[inb]]
    zz = z[ok][inb]
    # robust IRLS fit on the central 90% of depths
    lo, hi = np.percentile(d, [4, 96])
    m = (d >= lo) & (d <= hi) & (zz > 0.02)
    if m.sum() < 30:
        return None
    d, zz = d[m], zz[m]
    best = None
    rng = np.random.default_rng(7)
    for _ in range(6):
        try:
            A = np.stack([d, np.ones_like(d)], 1)
            coef, *_ = np.linalg.lstsq(A, zz, rcond=None)
        except np.linalg.LinAlgError:
            return None
        resid = np.abs(A @ coef - zz)
        scale = 1.4826 * np.median(resid) + 1e-9
        keep = resid < 3 * scale
        if keep.sum() >= 30:
            coef, *_ = np.linalg.lstsq(A[keep], zz[keep], rcond=None)
            resid = np.abs(A @ coef - zz)
            keep = resid < 3 * scale
        inlier_frac = float(keep.mean())
        if best is None or inlier_frac > best[1]:
            best = (coef, inlier_frac)
    coef, frac = best
    if frac < 0.55:
        return None
    return float(coef[0]), float(coef[1]), frac


def write_ply(path, xyz, rgb):
    n = len(xyz)
    header = (f"ply\nformat binary_little_endian 1.0\nelement vertex {n}\n"
              "property float x\nproperty float y\nproperty float z\n"
              "property uchar red\nproperty uchar green\nproperty uchar blue\n"
              "end_header\n").encode()
    data = np.empty(n, dtype=[("xyz", "<f4", 3), ("rgb", "u1", 3)])
    data["xyz"] = xyz.astype(np.float32)
    data["rgb"] = rgb.astype(np.uint8)
    with open(path, "wb") as fh:
        fh.write(header)
        fh.write(data.tobytes())


def main() -> int:
    if 'DATASET_DIR' not in os.environ:
        from pipeline_guard import reject_retired_temporal_pipeline
        reject_retired_temporal_pipeline()
    cams_rec = json.loads((Path(os.environ.get("SFM_CAMERAS", str(BASE / "analysis-merged" / "sfm-cameras.json")))).read_text())
    cam = cams_rec["camera"]
    model = cam["model"]
    if model not in ("OPENCV", "RADIAL", "SIMPLE_RADIAL", "FULL_OPENCV"):
        print(f"camera model {model}: adjust undistortion handling", file=sys.stderr)
        return 1
    p = cam["params"]
    if model == "OPENCV":
        fx, fy, cx, cy, k1, k2, p1, p2 = p
    elif model == "FULL_OPENCV":
        fx, fy, cx, cy = p[:4]
        k1, k2, p1, p2 = p[4], p[5], p[8], p[9]
    else:  # SIMPLE_RADIAL / RADIAL
        fx, fy, cx, cy = p[:4]
        k1 = p[4]
        k2 = p[5] if model == "RADIAL" else 0.0
        p1 = p2 = 0.0
    dist = (k1, k2, p1, p2)
    # MoGe maps are 598x1064, while source frames / COLMAP K are 1080x1920.
    # Scaling only the image and retaining full-resolution K misprojects seeds.
    first_depth = next((DS / "depths").glob("*.png"), None)
    if first_depth is None:
        raise RuntimeError(f"No depth maps in {DS}; run 04_geometry.py for this frame first")
    map_h, map_w = load_depth(first_depth).shape
    fx, fy = fx * map_w / cam["width"], fy * map_h / cam["height"]
    cx, cy = cx * map_w / cam["width"], cy * map_h / cam["height"]
    K = (fx, fy, cx, cy)

    model_cameras, imgs, pts_model = read_model(Path(os.environ.get("SPARSE_MODEL", str(BASE / "colmap-gpu" / "merged" / "sparse" / "0"))))
    if len(model_cameras)!=1 or len({im['camera_id'] for im in imgs.values()})!=1:
        raise RuntimeError('Seed one calibrated component at a time; a merged two-calibration model cannot use one shared K.')
    names_sorted = sorted(imgs, key=lambda i: imgs[i]["name"])
    names = [imgs[i]["name"] for i in names_sorted]
    P_w = np.array([pts_model[pid]["xyz"] for pid in pts_model]) \
        if pts_model else np.zeros((0, 3))
    print(f"sparse points: {len(P_w)}, images: {len(names)}", flush=True)

    depths_dir = DS / "depths"
    frames_dir = DS / "images"

    # pose arrays in sorted order
    R_arr, t_arr, C_arr = [], [], []
    for i in names_sorted:
        im = imgs[i]
        R = qvec_to_rotmat(im["qvec"])
        R_arr.append(R)
        t_arr.append(im["tvec"])
        C_arr.append(-R.T @ im["tvec"])
    R_arr = np.array(R_arr)
    t_arr = np.array(t_arr)
    C_arr = np.array(C_arr)
    spread = float(np.linalg.norm(C_arr.max(0) - C_arr.min(0)))
    voxel = spread / VOXEL_DIVISOR

    # 1) per-frame alignment
    aligns = []
    alignment_records=[]
    for i, name in enumerate(names):
        dpath = depths_dir / (Path(name).stem + ".png")
        d = load_depth(dpath) if dpath.exists() else None
        if d is None or len(P_w) < 40:
            aligns.append(None)
            continue
        # Only this image's associated, observed tracks may calibrate its depth.
        # Projecting every component point includes occluded background surfaces.
        observed=imgs[names_sorted[i]].get('point3D_ids',np.empty(0,dtype=int))
        observed=np.unique(observed[observed>=0])
        observed=np.array([pts_model[int(pid)]['xyz'] for pid in observed if int(pid) in pts_model],dtype=float).reshape(-1,3)
        fit = fit_alignment(d, observed, R_arr[i], t_arr[i], K, dist)
        if fit is not None and (not np.isfinite(fit[0]) or fit[0]<=0):fit=None
        aligns.append(fit)
        alignment_records.append({'name':name,'observed_points':len(observed),'fit':list(map(float,fit)) if fit else None})
    ok_align = [(i, a) for i, a in enumerate(aligns) if a]
    print(f"aligned {len(ok_align)}/{len(names)} frames "
          f"(median inlier frac "
          f"{np.median([a[2] for _, a in ok_align]) if ok_align else 0:.2f})",
          flush=True)
    if len(ok_align) < len(names) * 0.6:
        print("too few depth alignments", file=sys.stderr)
        return 1

    # A retained RGB/normal-only view may be first in time. Its missing depth
    # must not prevent seeding the other aligned images.
    h, w = map_h, map_w
    vv, uu = np.mgrid[0:h:GRID, 0:w:GRID]
    uu, vv = uu.ravel(), vv.ravel()
    xn = (uu - cx) / fx
    yn = (vv - cy) / fy
    xu, yu = undistort_points(xn, yn, *dist)
    dirs = np.stack([xu, yu, np.ones_like(xu)], 1)  # z-depth form

    all_xyz, all_rgb, per_frame = [], [], []
    rng = np.random.default_rng(11)
    for i, a in ok_align:
        if i % FRAME_STRIDE:
            continue
        name = names[i]
        d = load_depth(depths_dir / (Path(name).stem + ".png"))
        alpha, beta, frac = a
        z = alpha * d[vv, uu] + beta
        valid = z > 0.05
        if valid.sum() < 100:
            continue
        X_cam = dirs[valid] * z[valid][:, None]
        X_w = X_cam @ R_arr[i] + t_arr[i]  # R^T (Xc - t) == Xc @ R + ... note below
        # COLMAP: x_cam = R * X_w + t  =>  X_w = R^T (x_cam - t)
        X_w = (X_cam - t_arr[i]) @ R_arr[i]

        # multi-view consistency against nearby registered frames
        agree = np.zeros(valid.sum(), dtype=int)
        checked = 0
        for off in (-3, -2, -1, 1, 2, 3):
            j = i + off
            if j < 0 or j >= len(names) or aligns[j] is None:
                continue
            checked += 1
            aj = aligns[j]
            Xc_j = X_w @ R_arr[j].T + t_arr[j]
            zj = Xc_j[:, 2]
            good = zj > 0.05
            xn_j = np.where(good, Xc_j[:, 0] / np.maximum(zj, 1e-9), 0)
            yn_j = np.where(good, Xc_j[:, 1] / np.maximum(zj, 1e-9), 0)
            xd_j, yd_j = distort_points(xn_j, yn_j, *dist)
            uj = (fx * xd_j + cx).astype(int)
            vj = (fy * yd_j + cy).astype(int)
            inb = good & (uj >= 0) & (uj < w) & (vj >= 0) & (vj < h)
            dj = alpha * 0  # neighbor uses its own fit
            alpha_j, beta_j, _ = aj
            dj = load_depth(depths_dir / (Path(names[j]).stem + ".png"))[vj.clip(0, h - 1),
                                                                        uj.clip(0, w - 1)]
            dz = alpha_j * dj + beta_j
            agree[inb & (np.abs(zj - dz) <= CONSIST_TOL * np.maximum(zj, 1e-9))] += 1
        if checked == 0:
            continue
        keep = agree >= CONSIST_MIN_AGREE
        if keep.sum() < 50:
            per_frame.append({"name": name, "n": 0, "agree_frac": 0.0})
            continue

        xv = X_w[keep]
        # rgb from the frame image at kept pixels
        img = cv2.imread(str(frames_dir / name))
        img = cv2.resize(img, (w, h), interpolation=cv2.INTER_AREA)
        px_u, px_v = uu[valid][keep], vv[valid][keep]
        rgb = img[px_v.clip(0, h - 1), px_u.clip(0, w - 1)][:, ::-1]
        all_xyz.append(xv)
        all_rgb.append(rgb)
        per_frame.append({"name": name, "n": int(keep.sum()),
                          "agree_frac": float(keep.mean())})

    xyz = np.concatenate(all_xyz)
    rgb = np.concatenate(all_rgb)
    keys = np.floor(xyz / voxel).astype(np.int64)
    _, uniq = np.unique(keys, axis=0, return_index=True)
    xyz, rgb = xyz[uniq], rgb[uniq]
    if len(xyz) > MAX_POINTS:
        sel = rng.choice(len(xyz), MAX_POINTS, replace=False)
        xyz, rgb = xyz[sel], rgb[sel]
    write_ply(OUT_PLY, xyz, rgb)

    stats = {
        "ply": str(OUT_PLY), "n_points": int(len(xyz)),
        "voxel": voxel, "camera_spread": spread,
        "grid": GRID, "frame_stride": FRAME_STRIDE,
        "consistency": f">={CONSIST_MIN_AGREE}/{CONSIST_NEIGHBORS} within {CONSIST_TOL}",
        "aligned_frames": len(ok_align),
        "per_frame": per_frame,
        "alignment_records":alignment_records,
        "input_depth_convention":os.environ.get('SEED_DEPTH_CONVENTION','relative depth aligned to observed sparse z-depth'),
        "intrinsics_grid":{"width":map_w,"height":map_h,"K":list(map(float,K))},
        "frame_contract":str(DS/'FRAME.json'),
    }
    OUT_JSON.write_text(json.dumps(stats, indent=1))
    print(f"seed cloud: {len(xyz)} points -> {OUT_PLY}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
