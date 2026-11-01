"""Gate fresh SfM, apply one +Y-up similarity, and build a train-only sparse seed.

Default is an audit only. --apply writes NEW output paths; nothing is overwritten.
All selected train/eval camera poses remain available for rendering, but eval
observations never enter exported tracks or seed colors. SfM itself used every
image: this is a photometric timestamp holdout, not independent geometry truth.
No previous reconstruction or learned-depth files are opened.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import sys
import numpy as np
import cv2

HERE = Path(__file__).resolve().parent
WORK = HERE.parent
FRESH = Path('C:/Users/bombe/OneDrive/Documents/ChatGPT/Ruang Kamare/roomscan-reconstruction/data/20261031_OSMO360/clean-v3').resolve()
sys.path.insert(0, str(HERE.parents[1] / 'osmo-reconstruct-20261031'))
from seed_fisheye import read_model, write_model_text, qvec_to_rotmat, rotmat_to_qvec, Fisheye


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def fresh_path(path):
    path = path.resolve()
    if not path.is_relative_to(FRESH):
        raise ValueError(f'Input/output must belong to the new clean-v3 run: {path}')
    return path


def model_paths(root):
    def exists(p):
        return (p / 'cameras.bin').is_file() or (p / 'cameras.txt').is_file()
    if exists(root):
        return [root]
    base = root / 'sparse' if (root / 'sparse').is_dir() else root
    return [p for p in sorted(base.iterdir()) if p.is_dir() and exists(p)]


def split_name(name):
    stem = Path(name).stem
    train, ev = 'train' in stem, 'eval' in stem
    if train == ev:
        raise ValueError(f'Exactly one train/eval marker is required in basename: {name}')
    return 'train' if train else 'eval'


def coverage(images, records, rules, minimum_fraction):
    names = {im['name'].replace('\\', '/') for im in images.values()}
    expected = {f'cam{c}/{r["filename"]}' for r in records for c in range(2)}
    unexpected = names - expected
    if unexpected:
        raise ValueError(f'SfM includes images outside this new selection: {sorted(unexpected)[:8]}')
    pairs = {r['source_frame']: all(f'cam{c}/{r["filename"]}' in names for c in range(2)) for r in records}
    complete_frames = [r['source_frame'] for r in records if pairs[r['source_frame']]]
    result = {'registered_images': len(names), 'expected_images': len(expected),
              'image_fraction': len(names) / len(expected),
              'registered_complete_pairs': sum(pairs.values()), 'expected_pairs': len(records),
              'complete_pair_fraction': sum(pairs.values()) / len(records),
              'missing_images': sorted(expected - names), 'regions': [],
              'largest_complete_pair_gap_source_frames': int(np.diff(complete_frames).max()) if len(complete_frames) > 1 else None}
    result['passes'] = result['image_fraction'] >= minimum_fraction and result['complete_pair_fraction'] >= minimum_fraction
    for region in rules['regions']:
        a, b = int(region['source_frame_min']), int(region['source_frame_max'])
        selected = [r for r in records if a <= r['source_frame'] <= b]
        if not selected:
            raise ValueError(f'No selected timestamps in coverage region {region["name"]}')
        count = sum(pairs[r['source_frame']] for r in selected)
        frac = count / len(selected)
        passed = frac >= region.get('minimum_pair_fraction', minimum_fraction) and count >= region.get('minimum_complete_pairs', 2)
        registered = [r['source_frame'] for r in selected if pairs[r['source_frame']]]
        rr = {'name': region['name'], 'source_frame_min': a, 'source_frame_max': b,
              'selected_pairs': len(selected), 'complete_pairs': count, 'complete_pair_fraction': frac,
              'registered_source_frames': registered,
              'largest_pair_gap_source_frames': int(np.diff(registered).max()) if len(registered) > 1 else None,
              'minimum_presence_satisfied': passed, 'enforced_as_gate': region.get('enforce', True)}
        result['regions'].append(rr)
        if region.get('enforce', True):
            result['passes'] &= passed
    return result


def trajectory_continuity(images, records, rules):
    by_name = {im['name'].replace('\\', '/'): im for im in images.values()}
    frames, centers = [], []
    for record in records:
        names = [f'cam{c}/{record["filename"]}' for c in range(2)]
        if not all(n in by_name for n in names):
            continue
        pair = [by_name[n] for n in names]
        center = np.mean([-qvec_to_rotmat(im['qvec']).T @ im['tvec'] for im in pair], axis=0)
        frames.append(record['source_frame']); centers.append(center)
    if len(frames) < 2:
        return {'complete_pairs': len(frames), 'warning': 'Insufficient trajectory support'}
    delta = np.diff(frames); distance = np.linalg.norm(np.diff(centers, axis=0), axis=1)
    speed = distance / delta
    median_speed = float(np.median(speed))
    details = []
    for region in rules['regions']:
        a, b = region['source_frame_min'], region['source_frame_max']
        # Include crossing segments at each region boundary, not only internal steps.
        which = (np.asarray(frames[:-1]) <= b) & (np.asarray(frames[1:]) >= a)
        inds = np.flatnonzero(which)
        details.append({'name': region['name'], 'segments': [
            {'from_source_frame': int(frames[j]), 'to_source_frame': int(frames[j+1]),
             'gap_source_frames': int(delta[j]), 'center_step_source_units': float(distance[j]),
             'speed_relative_to_full_trajectory_median': float(speed[j] / max(median_speed, 1e-12))}
            for j in inds],
            'largest_crossing_gap_source_frames': int(delta[which].max()) if len(inds) else None,
            'max_speed_relative_to_median': float(speed[which].max()/max(median_speed, 1e-12)) if len(inds) else None})
    return {'complete_pairs': len(frames), 'source_units_nonmetric': True,
            'median_center_step': float(np.median(distance)), 'maximum_center_step': float(distance.max()),
            'median_motion_per_source_frame': median_speed, 'regions': details,
            'note': 'Large relative motion requires visual pose review; walking/turning speed is not constant. No arbitrary discontinuity threshold is imposed.'}


def repeat_visit_audit(images, points, records, rules, scale):
    """Report direct geometric links between camera paths revisiting the same room."""
    selected = {r['filename']: r['source_frame'] for r in records}
    regions = {r['name']: r for r in rules['regions']}
    image_frames = {iid: selected[Path(im['name']).name] for iid, im in images.items()}
    centers = {iid: -qvec_to_rotmat(im['qvec']).T@im['tvec'] for iid, im in images.items()}
    groups = []
    for group in rules.get('repeat_visit_groups', []):
        names = group['region_names']
        if len(names) != 2:
            raise ValueError('Repeat-visit audit currently requires exactly two regions')
        ids = []
        for name in names:
            region = regions[name]
            ids.append({iid for iid, frame in image_frames.items()
                        if region['source_frame_min'] <= frame <= region['source_frame_max']})
        visited_points = [set(), set()]
        strong_shared = []; all_shared = []
        for pid, point in points.items():
            stamps = []
            track_ids = set(map(int, point['image_ids']))
            for k in (0, 1):
                observed = track_ids & ids[k]
                if observed:
                    visited_points[k].add(pid)
                stamps.append({image_frames[iid] for iid in observed})
            if all(stamps):
                all_shared.append(pid)
                if min(map(len, stamps)) >= 2:
                    strong_shared.append(pid)
        row = {'name': group['name'], 'region_names': names, 'registered_images_per_visit': list(map(len, ids)),
               'sparse_points_observed_per_visit': list(map(len, visited_points)),
               'direct_cross_visit_sparse_tracks': len(all_shared),
               'cross_visit_tracks_with_two_timestamps_in_each_visit': len(strong_shared),
               'share_of_smaller_visit_point_set_linked': len(all_shared)/max(1, min(map(len, visited_points))),
               'units': 'normalized arbitrary world units; metric scale unknown', 'flags': [],
               'review_status': 'requires_visual_review',
               'interpretation': group.get('interpretation', '')}
        if all(ids):
            a = np.array([centers[i] for i in sorted(ids[0])])*scale
            b = np.array([centers[i] for i in sorted(ids[1])])*scale
            distance = np.linalg.norm(a[:, None, :] - b[None, :, :], axis=2)
            nearest_a, nearest_b = distance.min(axis=1), distance.min(axis=0)
            row['camera_centroid_separation'] = float(np.linalg.norm(a.mean(0)-b.mean(0)))
            row['closest_cross_visit_camera_distance'] = float(distance.min())
            row['first_to_second_nearest_camera_distance'] = {'median': float(np.median(nearest_a)), 'p95': float(np.percentile(nearest_a, 95))}
            row['second_to_first_nearest_camera_distance'] = {'median': float(np.median(nearest_b)), 'p95': float(np.percentile(nearest_b, 95))}
            row['within_visit_camera_radius_p95'] = [float(np.percentile(np.linalg.norm(x-x.mean(0), axis=1), 95)) for x in (a, b)]
        else:
            row['flags'].append('one_visit_has_no_registered_cameras')
        if not all_shared:
            row['flags'].append('no_direct_cross_visit_feature_tracks')
        elif not strong_shared:
            row['flags'].append('cross_visit_tracks_lack_two_timestamps_per_visit')
        row['limitation'] = 'Low residuals or shared tracks do not independently prove that a room is unfolded; visually inspect source-aligned camera paths and sparse structure.'
        groups.append(row)
    return groups


def save_continuity_preview(path, images, points, records, rules, rotation, scale, translation):
    from PIL import Image, ImageDraw
    xyz = np.array([point['xyz'] for point in points.values()])
    xyz = scale*(xyz@rotation.T) + translation
    selected = {r['filename']: r['source_frame'] for r in records}
    trajectory = []
    for im in images.values():
        if not im['name'].replace('\\', '/').startswith('cam0/'):
            continue
        c = -qvec_to_rotmat(im['qvec']).T@im['tvec']
        trajectory.append((selected[Path(im['name']).name], scale*(rotation@c)+translation))
    trajectory.sort(key=lambda item: item[0])
    canvas = Image.new('RGB', (1600, 900), (20, 27, 35)); draw = ImageDraw.Draw(canvas)
    rng = np.random.default_rng(20261031)
    sample = xyz[rng.choice(len(xyz), min(50000, len(xyz)), replace=False)]
    colors = {'bathroom': (70, 230, 240), 'bathroom_second': (245, 85, 220)}
    for axes, box, title in [((0, 2), (45, 65, 730, 735), 'Top: X / Z'), ((0, 1), (835, 65, 720, 735), 'Side: X / Y')]:
        ax, ay = axes; x0, y0, width, height = box
        lo, hi = np.percentile(xyz[:, [ax, ay]], [.5, 99.5], axis=0)
        span = np.maximum(hi-lo, 1e-5); factor = min(width/span[0], height/span[1]); mid = (hi+lo)/2
        def project(point):
            return int(x0+width/2+(point[ax]-mid[0])*factor), int(y0+height/2-(point[ay]-mid[1])*factor)
        draw.text((x0, y0-30), title, fill='white')
        for point in sample:
            xx, yy = project(point)
            if x0 <= xx < x0+width and y0 <= yy < y0+height:
                draw.point((xx, yy), fill=(80, 118, 143))
        line = [project(c) for _, c in trajectory]
        if len(line) > 1:
            draw.line(line, fill=(230, 190, 85), width=2)
        for region in rules['regions']:
            if region['name'] not in colors:
                continue
            color = colors[region['name']]
            local = [(f, c) for f, c in trajectory if region['source_frame_min'] <= f <= region['source_frame_max']]
            if len(local) > 1:
                draw.line([project(c) for _, c in local], fill=color, width=5)
            for f, c in local:
                xx, yy = project(c); draw.ellipse((xx-3, yy-3, xx+3, yy+3), fill=color)
            if local:
                xx, yy = project(local[len(local)//2][1]); draw.text((xx+6, yy+6), region['name'], fill=color)
    draw.text((45, 835), 'Fresh SfM only. Yellow: full camera0 path. Cyan: first bathroom visit. Magenta: second bathroom visit.', fill=(220, 225, 235))
    draw.text((45, 860), 'One global similarity; nonmetric units. Camera proximity / cross-visit tracks need visual review, not a guessed merge.', fill=(220, 225, 235))
    canvas.save(path)


def reprojection(cameras, images, points):
    """Reproject actual XYZ independently; ignore native point.error placeholder."""
    all_errors, per_image = [], []
    by_camera = {}; angular_bins = {}
    invalid = 0
    for im in images.values():
        ix = np.array([i for i, pid in enumerate(im['point3D_ids']) if int(pid) in points], dtype=int)
        if not len(ix):
            continue
        xyz = np.array([points[int(im['point3D_ids'][i])]['xyz'] for i in ix])
        r = qvec_to_rotmat(im['qvec'])
        pc = xyz @ r.T + im['tvec']
        pred, valid = Fisheye(cameras[im['camera_id']]).project(pc)
        err = np.linalg.norm(pred - im['points2D_xy'][ix], axis=1)
        valid &= np.isfinite(err)
        invalid += int((~valid).sum())
        errors = err[valid]
        by_camera.setdefault(im['camera_id'], []).append(errors)
        theta = np.rad2deg(np.arctan2(np.linalg.norm(pc[:, :2], axis=1), pc[:, 2]))
        for lo, hi in ((0, 40), (40, 70), (70, 85), (85, 99), (99, 180)):
            select = valid & (theta >= lo) & (theta < hi)
            if select.any():
                angular_bins.setdefault((im['camera_id'], lo, hi), []).append(err[select])
        all_errors.append(errors)
        per_image.append({'name': im['name'], 'split': split_name(im['name']), 'observations': len(errors),
                          'mean_native_px': float(errors.mean()) if len(errors) else None,
                          'p95_native_px': float(np.percentile(errors, 95)) if len(errors) else None})
    errors = np.concatenate(all_errors) if all_errors else np.array([])
    if not len(errors):
        raise ValueError('No reprojectable observations')
    def stats(chunks):
        x = np.concatenate(chunks)
        return {'observations': len(x), 'mean_native_px': float(x.mean()), 'median_native_px': float(np.median(x)),
                'p95_native_px': float(np.percentile(x, 95)), 'maximum_native_px': float(x.max())}
    return {'method': 'Independent OPENCV_FISHEYE reprojection, including behind-hemisphere rays; native point.error is not trusted',
            'observations': len(errors), 'invalid_projection_observations': invalid,
            'mean_native_px': float(errors.mean()), 'median_native_px': float(np.median(errors)),
            'p95_native_px': float(np.percentile(errors, 95)), 'p99_native_px': float(np.percentile(errors, 99)),
            'maximum_native_px': float(errors.max()), 'per_image': per_image,
            'per_camera': [{'camera_id': cid, **stats(chunks)} for cid, chunks in sorted(by_camera.items())],
            'per_camera_angle_bin': [{'camera_id': key[0], 'theta_min_deg': key[1], 'theta_max_deg': key[2], **stats(chunks)}
                                     for key, chunks in sorted(angular_bins.items())]}


def rig_pair_audit(cameras, images, records, scale):
    by_name = {im['name'].replace('\\', '/'): im for im in images.values()}
    rows, rotations, translations = [], [], []
    for record in records:
        names = [f'cam{c}/{record["filename"]}' for c in (0, 1)]
        if not all(name in by_name for name in names):
            continue
        a, b = [by_name[name] for name in names]
        ra, rb = qvec_to_rotmat(a['qvec']), qvec_to_rotmat(b['qvec'])
        ca, cb = -ra.T@a['tvec'], -rb.T@b['tvec']
        rotation = rb@ra.T
        translation = b['tvec'] - rotation@a['tvec']
        rotations.append(rotation); translations.append(translation)
        rows.append({'source_frame': record['source_frame'], 'baseline_source_units': float(np.linalg.norm(cb-ca)),
                     'baseline_normalized_units': float(scale*np.linalg.norm(cb-ca))})
    if not rows:
        return {'complete_pairs': 0, 'flags': ['no_complete_pairs']}
    u, _, vh = np.linalg.svd(np.mean(rotations, axis=0))
    d = np.eye(3); d[-1, -1] = np.linalg.det(u@vh)
    mean_r = u@d@vh
    angle = lambda r: math.degrees(math.acos(float(np.clip((np.trace(r)-1)/2, -1, 1))))
    spread = np.array([angle(r@mean_r.T) for r in rotations])
    baseline = np.array([row['baseline_normalized_units'] for row in rows])
    relative_t = np.array(translations)*scale
    median_baseline = float(np.median(baseline))
    params = []
    for prefix in ('cam0', 'cam1'):
        camera_ids = sorted({im['camera_id'] for im in images.values() if im['name'].replace('\\', '/').startswith(prefix+'/')})
        params.append({'prefix': prefix, 'camera_ids': camera_ids,
                       'cameras': [{**{k: v for k, v in cameras[cid].items() if k != 'params'},
                                    'params': cameras[cid]['params'].tolist()} for cid in camera_ids]})
    result = {'complete_pairs': len(rows), 'units': 'normalized arbitrary world units; not measured metres',
              'baseline': {'minimum': float(baseline.min()), 'median': median_baseline,
                           'maximum': float(baseline.max()), 'p95': float(np.percentile(baseline, 95)),
                           'stddev': float(baseline.std()), 'coefficient_of_variation': float(baseline.std()/max(median_baseline, 1e-12))},
              'relative_rotation_mean_wxyz': rotmat_to_qvec(mean_r).tolist(),
              'relative_rotation_spread_deg': {'median': float(np.median(spread)), 'p95': float(np.percentile(spread, 95)), 'maximum': float(spread.max())},
              'cam1_from_cam0_translation_median_normalized': np.median(relative_t, axis=0).tolist(),
              'camera_groups': params, 'pairs': rows, 'flags': []}
    if spread.max() > .1:
        result['flags'].append('relative_rotation_not_constant_to_0_1_degree')
    if baseline.std() > .01*max(median_baseline, 1e-12):
        result['flags'].append('baseline_varies_by_more_than_one_percent')
    if median_baseline <= 1e-8:
        result['flags'].append('baseline_remained_zero_or_numerically_negligible')
    return result


def similarity(images, source_up, unit_height):
    rotation = np.array([[1., 0, 0], [0, 0, 1], [0, -1, 0]]) if source_up == 'z' else np.eye(3)
    centers = np.array([-qvec_to_rotmat(im['qvec']).T @ im['tvec'] for im in images.values()])
    transformed = centers @ rotation.T
    med_height = float(np.median(transformed[:, 1]))
    if unit_height and med_height <= 1e-8:
        raise ValueError('Median camera height is not positive: source ground frame must be checked before height normalization')
    scale = 1.0 / med_height if unit_height else 1.0
    center = np.median(transformed, axis=0)
    center[1] = 0.0  # preserve the source ground plane, never infer/crop floor geometry
    translation = -scale * center
    assert abs(np.linalg.det(rotation) - 1) < 1e-12
    return rotation, scale, translation, {
        'rotation': rotation.tolist(), 'scale': scale, 'translation': translation.tolist(),
        'formula': 'X_new = scale * rotation @ X_source + translation',
        'source_up_declared_by_caller': source_up, 'coordinate_frame': '+Y up',
        'source_median_camera_height': med_height,
        'scale_basis': 'Median camera height = 1 arbitrary unit' if unit_height else 'Original arbitrary SfM scale preserved',
        'metric_scale_known': False,
        'note': 'One similarity for the whole scene and both lenses. No measured camera height, room-specific transform, crop, floor clamp, or inferred metric baseline.'}


def train_observations(cameras, images, points, images_dir, masks_dir, max_error, erode):
    """Rebuild tracks from mutually linked, visible train observations only."""
    tracks = {}
    sums = {}
    stats = {'train_observations_examined': 0, 'train_observations_kept': 0,
             'eval_rgb_files_opened': 0, 'missing_mask_files': [], 'train_files_read': 0}
    for iid, im in sorted(images.items()):
        if split_name(im['name']) != 'train':
            continue
        cam = cameras[im['camera_id']]
        mask_path = masks_dir / Path(im['name']).with_suffix('.png')
        mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
        if mask is None:
            raise FileNotFoundError(f'Mask required for seed: {mask_path}')
        if mask.shape != (cam['height'], cam['width']):
            raise ValueError(f'Mask size does not match native camera: {mask_path}')
        if erode:
            mask = cv2.erode(mask, np.ones((2*erode+1, 2*erode+1), np.uint8))
        idx = np.array([j for j, pid in enumerate(im['point3D_ids']) if int(pid) in points], dtype=int)
        if not len(idx):
            continue
        ids = im['point3D_ids'][idx]
        xyz = np.array([points[int(pid)]['xyz'] for pid in ids])
        obs = im['points2D_xy'][idx]
        r = qvec_to_rotmat(im['qvec'])
        pred, valid = Fisheye(cam).project(xyz @ r.T + im['tvec'])
        err = np.linalg.norm(pred - obs, axis=1)
        xy = np.floor(obs).astype(int)  # pixel centers are j+0.5
        valid &= np.isfinite(err) & (err <= max_error)
        valid &= (xy[:, 0] >= 0) & (xy[:, 0] < cam['width']) & (xy[:, 1] >= 0) & (xy[:, 1] < cam['height'])
        j = np.flatnonzero(valid)
        valid[j] &= mask[xy[j, 1], xy[j, 0]] > 127
        j = np.flatnonzero(valid)
        stats['train_observations_examined'] += len(idx)
        if not len(j):
            continue
        rgb = cv2.imread(str(images_dir / im['name']), cv2.IMREAD_UNCHANGED)
        if rgb is None or rgb.shape[:2] != mask.shape or rgb.ndim != 3 or rgb.shape[2] < 3:
            raise ValueError(f'Cannot read native RGB matching camera: {im["name"]}')
        if rgb.dtype == np.uint16:
            rgb = np.rint(rgb[:, :, :3] / 257.0).astype(np.uint8)
        elif rgb.dtype != np.uint8:
            raise ValueError(f'Unsupported seed color dtype: {rgb.dtype}')
        stats['train_files_read'] += 1
        for k in j:
            pid = int(ids[k]); pidx = int(idx[k])
            point = points[pid]
            if not any(int(ii) == iid and int(jj) == pidx for ii, jj in zip(point['image_ids'], point['point2D_idxs'])):
                continue
            tracks.setdefault(pid, []).append((iid, pidx, float(err[k])))
            color = rgb[xy[k, 1], xy[k, 0], :3][::-1].astype(float)
            sums[pid] = sums.get(pid, np.zeros(3)) + color
            stats['train_observations_kept'] += 1
    return tracks, sums, stats


def sparse_ply(path, points):
    # Sparse points have no measured normals: omit those properties entirely.
    dtype = np.dtype([(k, '<f4') for k in ('x', 'y', 'z')] + [(k, 'u1') for k in ('red', 'green', 'blue')])
    data = np.empty(len(points), dtype=dtype)
    values = list(points.values())
    xyz = np.array([p['xyz'] for p in values]); rgb = np.array([p['rgb'] for p in values])
    for k, axis in enumerate(('x', 'y', 'z')):
        data[axis] = xyz[:, k]
    for k, channel in enumerate(('red', 'green', 'blue')):
        data[channel] = rgb[:, k]
    header = ('ply\nformat binary_little_endian 1.0\ncomment fresh SfM train-only sparse seed; nonmetric units\n'
              f'element vertex {len(data)}\n' + ''.join(f'property float {k}\n' for k in ('x', 'y', 'z')) +
              ''.join(f'property uchar {k}\n' for k in ('red', 'green', 'blue')) + 'end_header\n')
    with path.open('xb') as stream:
        stream.write(header.encode('ascii')); data.tofile(stream)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--sfm-root', type=Path, required=True)
    p.add_argument('--selection', type=Path, default=WORK/'frame-selection.json')
    p.add_argument('--coverage', type=Path, required=True, help='Verified bathroom and entry source-frame ranges')
    p.add_argument('--source-up', choices=('z', 'y'), required=True)
    p.add_argument('--unit-camera-height', action='store_true', help='Median camera height becomes one ARBITRARY unit')
    p.add_argument('--images-dir', type=Path, default=FRESH/'dataset/images')
    p.add_argument('--masks-dir', type=Path, default=FRESH/'dataset/masks')
    p.add_argument('--output-model', type=Path, default=FRESH/'dataset/sparse/0')
    p.add_argument('--seed', type=Path, default=FRESH/'dataset/seed-train-sparse.ply')
    p.add_argument('--min-registration', type=float, default=.90)
    p.add_argument('--max-observation-error-px', type=float, default=6.0)
    p.add_argument('--max-p95-error-px', type=float, default=5.0)
    p.add_argument('--mask-erode-px', type=int, default=2)
    p.add_argument('--minimum-seed-points', type=int, default=10000)
    p.add_argument('--report', type=Path, default=HERE/'fresh-sfm-preparation-audit.json')
    p.add_argument('--apply', action='store_true')
    a = p.parse_args()
    root = fresh_path(a.sfm_root)
    images_dir = fresh_path(a.images_dir); masks_dir = fresh_path(a.masks_dir)
    output = fresh_path(a.output_model); seed = fresh_path(a.seed)
    if not a.report.resolve().is_relative_to(HERE):
        raise ValueError('Report must be under the geometry helper directory')
    if a.apply and (seed.exists() or any((output/f).exists() for f in ('images.bin', 'images.txt', 'cameras.bin', 'cameras.txt', 'points3D.bin', 'points3D.txt'))):
        raise FileExistsError('Prepared model/seed already exists; refusing overwrite')
    selection = json.loads(a.selection.read_text()); records = selection['selected']
    rules = json.loads(a.coverage.read_text())
    if not rules.get('visually_verified', False):
        raise ValueError('Coverage intervals must be visually verified first')
    if not {'bathroom', 'entry'}.issubset({r['name'] for r in rules['regions']}):
        raise ValueError('Coverage rules must explicitly include bathroom and entry')
    for r in records:
        if split_name(r['filename']) != r['split']:
            raise ValueError('Selected split marker disagrees with recorded split')
        for lens in (0, 1):
            if not (images_dir/f'cam{lens}'/r['filename']).is_file():
                raise FileNotFoundError(f'Missing selected source image: cam{lens}/{r["filename"]}')
    summaries = []
    for path in model_paths(root):
        cams, ims, pts = read_model(path)
        summary = coverage(ims, records, rules, a.min_registration)
        summaries.append({'path': str(path), 'points': len(pts), **summary})
    report = {'source_root': str(root), 'selection_sha256': digest(a.selection), 'coverage_rules': rules,
              'minimum_registration_fraction': a.min_registration, 'components': summaries,
              'old_reconstruction_opened': False, 'learned_depth_opened': False,
              'heldout_definition': 'Both lenses of a selected timestamp excluded from photometric training and seed RGB/tracks; camera poses and triangulation were solved with all SfM images',
              'applied': False}
    eligible = [s for s in summaries if s['passes']]
    if not eligible:
        save(a.report, report)
        raise RuntimeError('No single component passes registration and room coverage gates; inspect the report, do not merge by guesswork')
    best = max(eligible, key=lambda s: (s['registered_complete_pairs'], s['registered_images'], s['points']))
    cameras, images, points = read_model(Path(best['path']))
    measured = reprojection(cameras, images, points)
    report['selected_component'] = best['path']; report['reprojection'] = measured
    report['trajectory_continuity'] = trajectory_continuity(images, records, rules)
    if measured['p95_native_px'] > a.max_p95_error_px or measured['invalid_projection_observations']:
        save(a.report, report)
        raise RuntimeError('Fresh SfM failed the independently recomputed reprojection gate')
    rotation, scale, translation, transform = similarity(images, a.source_up, a.unit_camera_height)
    report['rig_pair_audit'] = rig_pair_audit(cameras, images, records, scale)
    report['repeat_visit_audit'] = repeat_visit_audit(images, points, records, rules, scale)
    preview = a.report.with_name(a.report.stem+'-continuity.png')
    save_continuity_preview(preview, images, points, records, rules, rotation, scale, translation)
    report['continuity_preview'] = str(preview.resolve())
    tracks, colors, seed_stats = train_observations(cameras, images, points, images_dir, masks_dir,
                                                  a.max_observation_error_px, a.mask_erode_px)
    newpoints = {}
    for pid, track in tracks.items():
        timestamps = {Path(images[iid]['name']).stem for iid, _, _ in track}
        if len(timestamps) < 2:
            continue
        point = points[pid]
        newpoints[pid] = {**point, 'xyz': scale*(rotation @ point['xyz']) + translation,
                          'rgb': np.rint(colors[pid]/len(track)).clip(0, 255).astype(np.uint8),
                          'error': float(np.mean([r for _, _, r in track])), 'track_len': len(track),
                          'image_ids': np.array([i for i, _, _ in track], dtype=np.int32),
                          'point2D_idxs': np.array([j for _, j, _ in track], dtype=np.int32)}
    allowed = {(iid, j): pid for pid in newpoints for iid, j, _ in tracks[pid]}
    newimages = {}; ray_max = 0.0
    for iid, im in images.items():
        r = qvec_to_rotmat(im['qvec']); center = -r.T @ im['tvec']
        rn = r @ rotation.T; cn = scale*(rotation @ center) + translation
        ids = np.full(len(im['point3D_ids']), -1, dtype=np.int64)
        if split_name(im['name']) == 'train':
            for j in range(len(ids)):
                if (iid, j) in allowed:
                    ids[j] = allowed[(iid, j)]
        newimages[iid] = {**im, 'qvec': rotmat_to_qvec(rn), 'tvec': -rn @ cn, 'point3D_ids': ids}
        sample = [int(pid) for pid in ids if pid >= 0][:128]
        if sample:
            raw = np.array([points[pid]['xyz'] for pid in sample]) @ r.T + im['tvec']
            out = np.array([newpoints[pid]['xyz'] for pid in sample]) @ rn.T + newimages[iid]['tvec']
            error = np.max(np.abs(raw/np.linalg.norm(raw, axis=1)[:, None] - out/np.linalg.norm(out, axis=1)[:, None]))
            ray_max = max(ray_max, float(error))
    if ray_max > 1e-8:
        raise RuntimeError('Global similarity failed projection ray invariance')
    if len(newpoints) < a.minimum_seed_points:
        report['seed_filter'] = {**seed_stats, 'points_retained': len(newpoints)}
        save(a.report, report)
        raise RuntimeError('Too few valid train-only sparse seed points')
    eval_ids = {iid for iid, im in images.items() if split_name(im['name']) == 'eval'}
    assert all(not (eval_ids & set(map(int, p['image_ids']))) for p in newpoints.values())
    assert all(np.all(newimages[i]['point3D_ids'] == -1) for i in eval_ids)
    seed_stats.update({'input_sparse_points': len(points), 'retained_train_only_points': len(newpoints),
                       'minimum_distinct_train_timestamps_per_point': 2,
                       'max_observation_error_native_px': a.max_observation_error_px,
                       'mask_erosion_native_px': a.mask_erode_px,
                       'train_pose_count': len(images)-len(eval_ids), 'eval_pose_count': len(eval_ids),
                       'eval_tracks_retained': 0, 'seed_color_source': 'Mean of valid train-image RGB samples only; native points3D RGB discarded'})
    report.update(transform=transform, seed_filter=seed_stats, projection_ray_identity_max_error=ray_max,
                  output_model=str(output), output_seed=str(seed))
    if a.apply:
        output.parent.mkdir(parents=True, exist_ok=True); seed.parent.mkdir(parents=True, exist_ok=True)
        write_model_text(output, cameras, newimages, newpoints)
        sparse_ply(seed, newpoints)
        # Round-trip the actual exported model, and verify heldout links again.
        cc, ii, pp = read_model(output)
        assert len(ii) == len(images) and len(pp) == len(newpoints)
        assert all(not (eval_ids & set(map(int, point['image_ids']))) for point in pp.values())
        assert all(np.all(ii[i]['point3D_ids'] == -1) for i in eval_ids)
        report['applied'] = True
        report['written_files_sha256'] = {str(f): digest(f) for f in [output/'cameras.txt', output/'images.txt', output/'points3D.txt', seed]}
    save(a.report, report)
    print(json.dumps({'selected_component': best['path'], 'registered_images': len(images),
                      'registered_complete_pairs': best['registered_complete_pairs'],
                      'p95_reprojection_native_px': measured['p95_native_px'], 'seed_points': len(newpoints),
                      'train_pose_count': len(images)-len(eval_ids), 'eval_pose_count': len(eval_ids),
                      'ray_identity_max_error': ray_max, 'metric_scale_known': False,
                      'applied': a.apply, 'report': str(a.report)}, indent=2))


if __name__ == '__main__':
    main()
