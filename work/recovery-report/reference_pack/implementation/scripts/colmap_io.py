"""Minimal COLMAP model reader/writer for the 20261027_IPHONE_WIDE project.

Supports text and binary cameras/images/points3D files. No pycolmap dependency.
Binary layouts follow COLMAP's scripts/python read_write_model.py.
"""
import struct
from pathlib import Path

import numpy as np

CAMERA_MODELS = {
    "SIMPLE_PINHOLE": 2, "PINHOLE": 2,
    "SIMPLE_RADIAL": 4, "RADIAL": 5, "OPENCV": 8,
    "OPENCV_FISHEYE": 8, "SIMPLE_RADIAL_FISHEYE": 4, "RADIAL_FISHEYE": 5,
    "THIN_PRISM_FISHEYE": 12, "FULL_OPENCV": 12,
}
# COLMAP CameraModelId enum order used in cameras.bin:
MODEL_ID_TO_NAME = {
    0: "SIMPLE_PINHOLE", 1: "PINHOLE", 2: "SIMPLE_RADIAL", 3: "RADIAL",
    4: "OPENCV", 5: "SIMPLE_RADIAL_FISHEYE", 6: "RADIAL_FISHEYE",
    7: "THIN_PRISM_FISHEYE", 8: "RAD_TAN_THIN_PRISM_FISHEYE",
    9: "FULL_OPENCV", 10: "FISHEYE_OPENCV", 11: "EQUIRECTANGULAR",
}


def _read_text_model(path: Path):
    cams, imgs, pts = {}, {}, {}
    for line in (path / "cameras.txt").read_text().splitlines():
        if not line or line.startswith("#"):
            continue
        f = line.split()
        cams[int(f[0])] = {"model": f[1], "width": int(f[2]), "height": int(f[3]),
                           "params": np.array([float(x) for x in f[4:]])}
    lines = iter((path / "images.txt").read_text().splitlines())
    for line in lines:
        if not line or line.startswith("#"):
            continue
        f = line.split()
        q = np.array([float(x) for x in f[1:5]])
        t = np.array([float(x) for x in f[5:8]])
        imgs[int(f[0])] = {"qvec": q, "tvec": t, "camera_id": int(f[8]),
                           "name": f[9]}
        # Consume the second record even when it is empty; it is never another
        # pose. The old parser silently treated observation rows as image rows.
        observation = next(lines, "").split()
        assert len(observation) % 3 == 0, "invalid COLMAP observation record"
        xy = np.array([[float(observation[j]), float(observation[j+1])]
                       for j in range(0, len(observation), 3)], dtype=float).reshape(-1, 2)
        ids = np.array([int(observation[j+2]) for j in range(0, len(observation), 3)], dtype=np.int64)
        imgs[int(f[0])].update(points2D_xy=xy, point3D_ids=ids,n_points2D=len(ids))
    for line in (path / "points3D.txt").read_text().splitlines():
        if not line or line.startswith("#"):
            continue
        f = line.split()
        pts[int(f[0])] = {"xyz": np.array([float(x) for x in f[1:4]]),
                          "rgb": np.array([int(x) for x in f[4:7]], np.uint8),
                          "error": float(f[7])}
    return cams, imgs, pts


def _read_bin_all(path: Path):
    cams = {}
    with open(path / "cameras.bin", "rb") as fh:
        (n,) = struct.unpack("<Q", fh.read(8))
        counts = {0: 3, 1: 4, 2: 4, 3: 5, 4: 8, 5: 4, 6: 6, 7: 12,
                  8: 15, 9: 12, 10: 8, 11: 1}
        for _ in range(n):
            cid, mid = struct.unpack("<ii", fh.read(8))
            w, h = struct.unpack("<QQ", fh.read(16))
            k = counts.get(mid, 8)
            params = np.frombuffer(fh.read(8 * k), dtype=np.float64)
            cams[cid] = {"model": MODEL_ID_TO_NAME.get(mid, str(mid)),
                         "width": w, "height": h, "params": params}

    imgs = {}
    with open(path / "images.bin", "rb") as fh:
        (n,) = struct.unpack("<Q", fh.read(8))
        for _ in range(n):
            iid = struct.unpack("<i", fh.read(4))[0]
            q = np.frombuffer(fh.read(32), dtype=np.float64)
            t = np.frombuffer(fh.read(24), dtype=np.float64)
            cid = struct.unpack("<i", fh.read(4))[0]
            name = b""
            while True:
                c = fh.read(1)
                if c in (b"\x00", b""):
                    break
                name += c
            (n2,) = struct.unpack("<Q", fh.read(8))
            raw = fh.read(24 * n2)
            data = np.frombuffer(raw, dtype=np.float64).reshape(n2, 3)
            pids = data[:, 2].view(np.int64) if n2 else np.zeros(0, np.int64)
            imgs[iid] = {"qvec": q, "tvec": t, "camera_id": cid,
                         "name": name.decode("utf-8"),
                         "points2D_xy": data[:, :2].copy(),
                         "point3D_ids": pids,
                         "n_points2D": n2}

    pts = {}
    with open(path / "points3D.bin", "rb") as fh:
        (n,) = struct.unpack("<Q", fh.read(8))
        for _ in range(n):
            pid = struct.unpack("<q", fh.read(8))[0]
            xyz = np.frombuffer(fh.read(24), dtype=np.float64)
            rgb = np.frombuffer(fh.read(3), dtype=np.uint8)
            (err,) = struct.unpack("<d", fh.read(8))
            (track_len,) = struct.unpack("<Q", fh.read(8))
            fh.read(8 * track_len)  # (image_id, point2D_idx) pairs
            pts[pid] = {"xyz": xyz, "rgb": rgb, "error": err, "track_len": track_len}
    return cams, imgs, pts


def read_model(path: Path):
    path = Path(path)
    if (path / "cameras.bin").exists():
        return _read_bin_all(path)
    return _read_text_model(path)


def qvec_to_rotmat(q: np.ndarray) -> np.ndarray:
    w, x, y, z = q
    return np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
        [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
    ])


def camera_centers(imgs) -> dict:
    out = {}
    for iid, im in imgs.items():
        R = qvec_to_rotmat(im["qvec"])
        out[iid] = -R.T @ im["tvec"]
    return out
