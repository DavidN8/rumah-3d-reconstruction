"""GPU LoFTR doorway correspondences backed by fresh MoGe metric depth."""
import json
from pathlib import Path
import cv2
import numpy as np
import torch
import kornia.feature as KF
from scipy.optimize import least_squares
from scipy.spatial.transform import Rotation
from colmap_io import read_model, qvec_to_rotmat
from importlib import import_module

BASE = Path(__file__).resolve().parents[1]


def intrinsics(cam):
    fx, fy, cx, cy = cam['params'][:4]
    return np.array([[fx, 0, cx], [0, fy, cy], [0, 0, 1.]])


def sample_depth(im, uv):
    if len(uv) == 0:
        return np.empty(0)
    p = BASE / 'analysis/metric-bridge/depths' / (Path(im['name']).stem + '.png')
    d = cv2.imread(str(p), -1)
    xy = uv * np.array([d.shape[1]/1080, d.shape[0]/1920])
    value = cv2.remap(d.astype(np.float32), xy[:, 0].astype(np.float32).reshape(-1, 1),
                      xy[:, 1].astype(np.float32).reshape(-1, 1), cv2.INTER_LINEAR).ravel() / 1000.
    return value


def estimate_scales(models):
    scales, records = [], []
    for comp, (cams, images, points) in enumerate(models):
        values = []
        for im in images.values():
            if not (BASE / 'analysis/metric-bridge/depths' / (Path(im['name']).stem+'.png')).exists():
                continue
            ids = im['point3D_ids']; keep = ids >= 0
            ids, uv = ids[keep], im['points2D_xy'][keep]
            r = qvec_to_rotmat(im['qvec']); xyz = np.array([points[int(k)]['xyz'] for k in ids])
            z = (xyz @ r.T + im['tvec'])[:, 2]
            metric = sample_depth(im, uv)
            good = (z > .02) & (metric > .15) & (metric < 12) & (uv[:, 0] > 30) & (uv[:, 0] < 1050)
            if good.sum() < 12:
                continue
            ratios = metric[good] / z[good]
            med = np.median(ratios); mad = np.median(np.abs(ratios-med))
            good_ratio = np.abs(ratios-med) < max(.08*med, 2.5*mad)
            scale = float(np.median(ratios[good_ratio]))
            rec = dict(component=comp, name=im['name'], metres_per_unit=scale,
                       samples=int(good.sum()), relative_mad=float(mad/med))
            records.append(rec)
            if mad/med < .18:
                values.append(scale)
        scales.append(float(np.median(values)))
    return scales, records


def backproject(uv, depth_m, cam, im, metres_per_unit):
    k = intrinsics(cam); dist = cam['params'][4:8]
    xy = cv2.undistortPoints(uv.reshape(-1, 1, 2), k, dist).reshape(-1, 2)
    xyz = np.c_[xy, np.ones(len(xy))] * (depth_m/metres_per_unit)[:, None]
    return (xyz - im['tvec']) @ qvec_to_rotmat(im['qvec'])


def main():
    torch.set_num_threads(16)
    assert torch.cuda.is_available(), 'GPU is required for dense matching'
    models = [read_model(BASE / f'colmap-gpu/ws/sparse/{z}') for z in (0, 1)]
    scales, records = estimate_scales(models)
    (BASE / 'analysis/metric-scales.json').write_text(json.dumps({'metres_per_native_unit': scales,
                                                              'frames': records}, indent=2))
    print('metric metres/native unit', scales, 'ratio',scales[0]/scales[1], flush=True)
    cache = BASE / 'analysis/models'; cache.mkdir(exist_ok=True)
    weights = torch.hub.load_state_dict_from_url('https://cmp.felk.cvut.cz/~mishkdmy/models/loftr_indoor_ds_new.ckpt',
                                                model_dir=str(cache), map_location='cpu', progress=False)
    matcher = KF.LoFTR(pretrained=None)
    matcher.load_state_dict(weights['state_dict']); matcher = matcher.eval().cuda()
    names = [[1358, 1366, 1374, 1382, 1386], [1390, 1394, 1398, 1402, 1406]]
    ims = [{int(Path(v['name']).stem.split('_')[-1]): v for v in m[1].values()} for m in models]
    tensors = {}
    for j in (0, 1):
        for n in names[j]:
            a = cv2.imread(str(BASE / 'frames' / ims[j][n]['name']), 0)
            a = cv2.resize(a, (384, 680), interpolation=cv2.INTER_AREA)
            tensors[j, n] = torch.from_numpy(a).float()[None, None].cuda()/255
    srcs, dsts, confidences, pair_stats, uvs0, uvs1 = [], [], [], [], [], []
    for na, nb in zip(names[0], names[1][::-1]):
        # Wider baselines supplement the adjacent pair; all have actual overlap.
        for nb in sorted(set([nb, 1390])):
            a, b = ims[0][na], ims[1][nb]
            with torch.inference_mode():
                pred = matcher({'image0': tensors[0, na], 'image1': tensors[1, nb]})
            ua, ub = [pred[k].cpu().numpy() * [1080/384, 1920/680] for k in ('keypoints0', 'keypoints1')]
            conf = pred['confidence'].cpu().numpy()
            good = conf > .25
            ua, ub, conf = ua[good], ub[good], conf[good]
            da, db = sample_depth(a, ua), sample_depth(b, ub)
            good = (da > .2) & (db > .2) & (da < 8) & (db < 8)
            ua, ub, da, db, conf = ua[good], ub[good], da[good], db[good], conf[good]
            if len(ua) < 8:
                print('insufficient LoFTR overlap', na, nb, len(ua), flush=True)
                continue
            src = backproject(ua, da, models[0][0][a['camera_id']], a, scales[0])
            dst = backproject(ub, db, models[1][0][b['camera_id']], b, scales[1])
            srcs.append(src); dsts.append(dst); confidences.append(conf); uvs0.append(ua); uvs1.append(ub)
            pair_stats.append(dict(a=na, b=nb, n=len(src)))
            print('LoFTR', na, nb, len(src), flush=True)
    src, dst = np.concatenate(srcs), np.concatenate(dsts)
    confidence = np.concatenate(confidences)
    np.savez_compressed(BASE / 'analysis/bridge-dense.npz', src=src, dst=dst, confidence=confidence,
                        uv0=np.concatenate(uvs0), uv1=np.concatenate(uvs1))
    # Metric scale is independently anchored. Optimize only rotation + translation.
    s = scales[0] / scales[1]
    old = json.loads((BASE/'backups/before-fix-20261027/model-merge.json').read_text())['similarity']
    r0, t0 = np.array(old['R']), np.array(old['t'])
    # Keep the initialization's doorway anchor while replacing its scale estimate.
    a, b = ims[0][1386], ims[1][1390]
    ra, rb = qvec_to_rotmat(a['qvec']), qvec_to_rotmat(b['qvec'])
    ca, cb = -ra.T @ a['tvec'], -rb.T @ b['tvec']
    t0 = cb - s*r0 @ ca
    def resid(x):
        r = Rotation.from_rotvec(x[:3]).as_matrix(); t = x[3:]
        return ((s * src @ r.T + t-dst)*scales[1]).ravel()
    sol = least_squares(resid, np.r_[Rotation.from_matrix(r0).as_rotvec(), t0], loss='soft_l1',
                        f_scale=.025, max_nfev=200)
    r = Rotation.from_rotvec(sol.x[:3]).as_matrix(); t=sol.x[3:]
    ds=np.linalg.norm(s*src@r.T+t-dst,axis=1)*scales[1]
    out=dict(method='GPU LoFTR, metric MoGe depth and independent sparse depth scale; robust rigid fit',
             scale=s,R=r.tolist(),t=t.tolist(),metric_scales=scales,pairs=pair_stats,matches=len(src),
             residual_metres=dict(median=float(np.median(ds)),p90=float(np.percentile(ds,90))),
             rotation_change_deg=float(Rotation.from_matrix(r@r0.T).magnitude()*180/np.pi),det=float(np.linalg.det(r)))
    (BASE/'analysis/bridge-dense-fit.json').write_text(json.dumps(out,indent=2))
    print(json.dumps(out,indent=2))


if __name__=='__main__':
    main()
