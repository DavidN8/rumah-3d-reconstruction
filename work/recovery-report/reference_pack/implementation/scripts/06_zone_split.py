"""20261027_IPHONE_WIDE Phase 4a: split the unified model into room zones.

The cut comes from a normalized spectral partition of the verified-pair
covisibility graph (matches.bin holds verified pairs with inlier counts), i.e.
the seam lands where the walk crosses least — the doorway. Each zone is then
materialized as a standalone COLMAP dataset in the SAME rigid world frame:

  zones/<zone>/images/    hardlinks to frames/
  zones/<zone>/sparse/0/  text COLMAP model: one shared camera, zone images,
                          zone points (non-zone observations written as -1)
  zones/<zone>/depths/    hardlinks from dataset-unified
  zones/<zone>/normals/   hardlinks from dataset-unified
  zones/<zone>/seed.ply   seed-cloud points nearest-owned by this zone
"""
import json
import os
import re
import shutil
import struct
import sys
from pathlib import Path

import numpy as np
import scipy.sparse as sp
from scipy.sparse.csgraph import laplacian
from scipy.sparse.linalg import eigsh
from scipy.spatial import cKDTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
from colmap_io import read_model, qvec_to_rotmat  # noqa: E402

BASE = Path(__file__).resolve().parents[1]
WS = Path(os.environ.get("SPARSE_WS", str(BASE / "colmap-gpu" / "merged")))
UPRIGHT = (WS / "sparse" / "0" / "FRAME.json").exists()
DS = BASE / "zones" / ("dataset-upright" if UPRIGHT else "dataset-unified")
# Existing checkpoints refer to zones/zone-* in the preserved legacy frame.
# A split of the corrected metre-scale model must use fresh datasets.
ZONES_DIR = BASE / ("zones-upright" if UPRIGHT else "zones")
MIN_INLIERS = 30
ZONE_NAMES = ["zone-0", "zone-1"]


def read_matches(path: Path):
    with open(path, "rb") as fh:
        (n,) = struct.unpack("<Q", fh.read(8))
        pairs = []
        for _ in range(n):
            i1, i2 = struct.unpack("<II", fh.read(8))
            (m,) = struct.unpack("<Q", fh.read(8))
            fh.read(8 * m)
            pairs.append((i1, i2, m))
    return pairs


def spectral_cut(n, rows, cols, weights, k=2):
    A = sp.coo_matrix((weights, (rows, cols)), shape=(n, n))
    A = (A + A.T).tocsr()
    L = laplacian(A, normed=True)
    nvec = min(k + 1, n - 1)
    vals, vecs = eigsh(L.astype(np.float64), k=nvec, sigma=-1e-6, which="LM")
    if k == 2:
        fiedler = vecs[:, 1]
        thr = (fiedler.min() + fiedler.max()) / 2
        for _ in range(50):
            c0 = fiedler[fiedler <= thr].mean()
            c1 = fiedler[fiedler > thr].mean()
            new_thr = (c0 + c1) / 2
            if abs(new_thr - thr) < 1e-12:
                thr = new_thr
                break
            thr = new_thr
        labels = (fiedler > thr).astype(int)
    else:
        from scipy.cluster.vq import kmeans2
        emb = vecs[:, 1:k + 1]
        centroids, labels = kmeans2(emb, k, minit="++", seed=7, iter=50)
        labels = labels.astype(int)
        # relabel by first appearance in time order for stable naming
        seen, remap = [], {}
        for lab in labels:
            if lab not in remap:
                remap[lab] = len(seen)
                seen.append(lab)
        labels = np.array([remap[l] for l in labels])
    return labels, float(vals[1])


def write_text_model(dst: Path, cams, imgs, pts, keep_images, keep_pids):
    dst.mkdir(parents=True, exist_ok=True)
    with open(dst / "cameras.txt", "w") as fh:
        for cid, c in cams.items():
            fh.write(f"{cid} {c['model']} {c['width']} {c['height']} "
                     + " ".join(repr(float(x)) for x in c["params"]) + "\n")
    keep_pids = set(int(p) for p in keep_pids)
    with open(dst / "images.txt", "w") as fh:
        fh.write("# Image list with two lines of data per image:\n"
                 "#   IMAGE_ID QW QX QY QZ TX TY TZ CAMERA_ID NAME\n"
                 "#   POINTS2D[] as (X, Y, POINT3D_ID)\n")
        for iid in sorted(keep_images):
            im = imgs[iid]
            fh.write(f"{iid} " + " ".join(repr(float(x)) for x in im["qvec"])
                     + " " + " ".join(repr(float(x)) for x in im["tvec"])
                     + f" {im['camera_id']} {im['name']}\n")
            xy = im.get("points2D_xy", np.zeros((0, 2)))
            pids = im.get("point3D_ids", np.zeros(0))
            if len(xy) == 0:
                fh.write("\n")
                continue
            lines = [f"{x!r} {y!r} {int(pid) if pid in keep_pids else -1}"
                     for (x, y), pid in zip(xy, pids)]
            fh.write(" ".join(lines) + "\n")
    with open(dst / "points3D.txt", "w") as fh:
        fh.write("# 3D point list with one line of data per point:\n"
                 "#   POINT3D_ID X Y Z R G B ERROR TRACK[] as (IMAGE_ID, POINT2D_IDX)\n")
        for pid in sorted(keep_pids):
            if pid not in pts:
                continue
            p = pts[pid]
            fh.write(f"{pid} " + " ".join(repr(float(v)) for v in p["xyz"])
                     + f" {p['rgb'][0]} {p['rgb'][1]} {p['rgb'][2]} {p['error']}\n")


def link(src: Path, dst: Path) -> None:
    if dst.exists():
        return
    try:
        os.link(src, dst)
    except OSError:
        shutil.copy2(src, dst)


def read_seed_ply(path: Path):
    with open(path, "rb") as fh:
        head = b""
        while b"end_header\n" not in head:
            chunk = fh.read(4096)
            if not chunk:
                raise ValueError("bad ply header")
            head += chunk
        m = re.search(rb"element vertex (\d+)\n", head)
        n = int(m.group(1))
        data_off = head.index(b"end_header\n") + len(b"end_header\n")
        fh.seek(data_off)
        body = fh.read(n * 15)
    data = np.frombuffer(body, dtype=np.uint8).reshape(n, 15)
    xyz = data[:, :12].copy().view("<f4").reshape(n, 3)
    rgb = data[:, 12:15]
    return xyz, rgb


def write_seed_ply(path: Path, xyz, rgb):
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
    """Zones by verified time boundaries (floorplan-checked) + nearest-camera
    point/seed ownership. ZONE_CUTS="1388,4090" -> zone-0: src<=1388 (kitchen),
    zone-1: 1389..4090 (living+corridor), zone-2: >=4091 (bedroom)."""
    from pipeline_guard import reject_retired_temporal_pipeline
    reject_retired_temporal_pipeline()
    cuts = [int(x) for x in os.environ.get("ZONE_CUTS", "1388,4090").split(",")]
    zone_names = [f"zone-{i}" for i in range(len(cuts) + 1)]
    cams, imgs, pts = read_model(WS / "sparse" / "0")
    def src_of(iid):
        return int(Path(imgs[iid]["name"]).stem.split("_")[-1])

    def zone_of_src(s):
        for k, c in enumerate(cuts):
            if s <= c:
                return k
        return len(cuts)

    assign = {}
    for iid, im in imgs.items():
        assign.setdefault(zone_of_src(src_of(iid)), []).append(iid)
    info = []
    for z in sorted(assign):
        members = sorted(assign[z], key=lambda i: src_of(i))
        assign[z] = members
        srcs = [src_of(i) for i in members]
        info.append({"zone": zone_names[z], "n_images": len(members),
                     "src_min": min(srcs), "src_max": max(srcs)})
    print(json.dumps(info, indent=1), flush=True)

    # point ownership: nearest camera (chunked for memory)
    all_iids = sorted(imgs)
    C = np.array([-(qvec_to_rotmat(imgs[i]["qvec"]).T @ imgs[i]["tvec"])
                  for i in all_iids])
    zone_of_cam = {i: zone_of_src(src_of(i)) for i in all_iids}
    pids_all = sorted(pts)
    P = np.array([pts[p]["xyz"] for p in pids_all])
    own = np.empty(len(P), dtype=np.int64)
    for s0 in range(0, len(P), 50000):
        chunk = P[s0:s0 + 50000]
        d2 = ((chunk[:, None, :] - C[None, :, :]) ** 2).sum(-1)
        own[s0:s0 + 50000] = np.array([zone_of_cam[all_iids[k]]
                                       for k in d2.argmin(1)])
    zone_pts = {z: set(np.array(pids_all)[own == z]) for z in assign}
    print("points:", {zone_names[z]: len(zone_pts[z]) for z in assign},
          flush=True)

    (ZONES_DIR / "zone-assign.json").write_text(json.dumps({
        "cuts": cuts, "info": info,
        "points": {zone_names[z]: len(zone_pts[z]) for z in assign},
    }, indent=1))

    for z in assign:
        zdir = ZONES_DIR / zone_names[z]
        (zdir / "images").mkdir(parents=True, exist_ok=True)
        for iid in assign[z]:
            link(BASE / "frames" / imgs[iid]["name"],
                 zdir / "images" / imgs[iid]["name"])
        for sub in ("depths", "normals"):
            src_dir = DS / sub
            if not src_dir.exists():
                continue
            (zdir / sub).mkdir(exist_ok=True)
            for iid in assign[z]:
                stem = Path(imgs[iid]["name"]).stem
                for ext in (".png", ".jpg"):
                    s_ = src_dir / (stem + ext)
                    if s_.exists():
                        link(s_, zdir / sub / s_.name)
                        break
        write_text_model(zdir / "sparse" / "0", cams, imgs, pts,
                         set(assign[z]), zone_pts[z])

    seed_ply = DS / "seed-cloud.ply"
    if seed_ply.exists():
        seed_xyz, seed_rgb = read_seed_ply(seed_ply)
        tree = cKDTree(C)
        _, nn = tree.query(seed_xyz, workers=-1)
        z_of_cam_vec = np.array([zone_of_cam[i] for i in all_iids])
        zz = z_of_cam_vec[nn]
        for z in assign:
            sel = zz == z
            write_seed_ply(ZONES_DIR / zone_names[z] / "seed.ply",
                           seed_xyz[sel], seed_rgb[sel])
            print(f"{zone_names[z]} seed: {int(sel.sum())} pts", flush=True)

    print("zones materialized", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
