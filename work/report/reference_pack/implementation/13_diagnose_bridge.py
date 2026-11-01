"""Measure the doorway bridge from independent COLMAP tracks, never speed."""
import json
from pathlib import Path
from collections import Counter
import cv2
import numpy as np
from scipy.spatial import cKDTree
from colmap_io import read_model, qvec_to_rotmat

BASE = Path(__file__).resolve().parents[1]


def umeyama(a, b):
    ac, bc = a - a.mean(0), b - b.mean(0)
    u, d, vt = np.linalg.svd(bc.T @ ac / len(a))
    sign = np.diag([1, 1, np.linalg.det(u @ vt)])
    r = u @ sign @ vt
    s = np.trace(np.diag(d) @ sign) / np.mean(np.sum(ac * ac, 1))
    return s, r, b.mean(0) - s * r @ a.mean(0)


def main():
    models = [read_model(BASE / f"colmap-gpu/ws/sparse/{i}") for i in (0, 1)]
    selected = [sorted(m[1].values(), key=lambda x: x["name"])[-14:] if j == 0
                else sorted(m[1].values(), key=lambda x: x["name"])[:18]
                for j, m in enumerate(models)]
    sift = cv2.SIFT_create(10000, contrastThreshold=0.015)
    feats = {}
    for j in (0, 1):
        for im in selected[j]:
            gray = cv2.imread(str(BASE / "frames" / im["name"]), 0)
            kp, desc = sift.detectAndCompute(gray, None)
            uv = np.array([k.pt for k in kp])
            keep = im["point3D_ids"] >= 0
            xy, pid = im["points2D_xy"][keep], im["point3D_ids"][keep]
            distance, nn = cKDTree(xy).query(uv)
            ids = np.where(distance < 1.6, pid[nn], -1)
            feats[j, im["name"]] = (uv, desc, ids)
    counts = Counter()
    bf = cv2.BFMatcher()
    pair_log = []
    # Keep geometric consensus per pair, then require repeated independent votes.
    for ia, a in enumerate(selected[0]):
        uva, da, pida = feats[0, a["name"]]
        for b in selected[1]:
            uvb, db, pidb = feats[1, b["name"]]
            forward = bf.knnMatch(da, db, k=2)
            backward = bf.knnMatch(db, da, k=2)
            back = {m.queryIdx: m.trainIdx for m, n in backward if m.distance < .72 * n.distance}
            good = [m for m, n in forward if m.distance < .72 * n.distance and back.get(m.trainIdx) == m.queryIdx]
            if len(good) < 10:
                continue
            ua = np.array([uva[m.queryIdx] for m in good]); ub = np.array([uvb[m.trainIdx] for m in good])
            f, mask = cv2.findFundamentalMat(ua, ub, cv2.USAC_MAGSAC, 1.2, .999, 10000)
            if mask is None:
                continue
            pairs = [(int(pida[m.queryIdx]), int(pidb[m.trainIdx])) for m, ok in zip(good, mask.ravel())
                     if ok and pida[m.queryIdx] >= 0 and pidb[m.trainIdx] >= 0]
            counts.update(set(pairs))
            pair_log.append({"a": a["name"], "b": b["name"], "matched": len(good), "tracks": len(pairs)})
        print("matched kitchen frame", ia + 1, "/", len(selected[0]), flush=True)
    keys = list(counts)
    src = np.array([models[0][2][a]["xyz"] for a, b in keys])
    dst = np.array([models[1][2][b]["xyz"] for a, b in keys])
    votes = np.array([counts[k] for k in keys])
    np.savez_compressed(BASE / "analysis/bridge-tracks.npz", src=src, dst=dst, votes=votes,
                        ids=np.array(keys))
    if len(keys)<4:
        (BASE / 'analysis/bridge-diagnostic.json').write_text(json.dumps({
            'accepted':False,'reason':'No shared independent sparse tracks in this weak doorway overlap',
            'unique_pairs':len(keys),'pair_log':pair_log},indent=2))
        print('Sparse-track bridge rejected; use metric depth and measured tiled floor constraints.')
        return
    rng = np.random.default_rng(42)
    best = None
    pool = np.flatnonzero(votes >= 2)
    if len(pool) < 6:
        pool = np.arange(len(keys))
    for _ in range(12000):
        k = rng.choice(pool, 4, replace=False)
        s, r, t = umeyama(src[k], dst[k])
        if not .1 < s < 4:
            continue
        d = np.linalg.norm(s * src @ r.T + t - dst, axis=1)
        mask = d < .012
        score = np.sum(np.minimum(votes[mask], 5))
        if best is None or score > best[0]:
            best = score, s, r, t, mask
    score, s, r, t, mask = best
    for _ in range(6):
        s, r, t = umeyama(src[mask], dst[mask])
        d = np.linalg.norm(s * src @ r.T + t - dst, axis=1)
        mask = d < .012
    out = {"method": "mutual SIFT / MAGSAC / independent 3D tracks / Sim3 RANSAC",
           "unique_pairs": len(keys), "repeated_pairs": int((votes >= 2).sum()),
           "inliers": int(mask.sum()), "scale": float(s), "R": r.tolist(), "t": t.tolist(),
           "inlier_median_units": float(np.median(d[mask])), "pair_log": pair_log}
    (BASE / "analysis/bridge-diagnostic.json").write_text(json.dumps(out, indent=2))
    print(json.dumps({k: v for k, v in out.items() if k != "pair_log"}, indent=2))


if __name__ == "__main__":
    main()
