"""Export upright 90-degree reference views from registered Osmo fisheye poses.

CPU only. Reads the normalized, Y-up COLMAP model through seed_fisheye's
strict reader. Reference images are calibrated reprojected/masked source
photos, NOT held-out validation renders or native pinhole photographs.
Run only once normalized poses and the actual exported mesh are ready.
"""
from __future__ import annotations
import argparse
import json
import math
from pathlib import Path
import re
import struct
import sys
import cv2
import numpy as np
from scipy.spatial.transform import Rotation
from seed_fisheye import read_model, qvec_to_rotmat, Fisheye

HERE = Path(__file__).resolve().parent
DEFAULT_RUN = Path(r'C:\Users\bombe\OneDrive\Documents\ChatGPT\Ruang Kamare\roomscan-reconstruction\data\20261031_OSMO360\lite-v1')
DEFAULT_OUT = HERE / 'exported-cameras.json'

def upright_frame(world_to_original):
    """Return world_from_virtual_opencv, Three.js [x,y,z,w], and forward.

    OpenCV virtual axes are right/down/forward. Three.js local axes are
    right/up/back, so their camera-to-world matrices differ by diag(1,-1,-1).
    """
    original_to_world = np.asarray(world_to_original, dtype=np.float64).T
    forward = original_to_world @ np.array([0., 0., 1.])
    forward[1] = 0.
    if np.linalg.norm(forward) < 1e-7:
        # A vertical optical axis does not define a heading: choose a heading
        # consistently from its right axis, then verify photo coverage later.
        right = original_to_world @ np.array([1., 0., 0.])
        right[1] = 0.
        if np.linalg.norm(right) < 1e-7:
            raise ValueError('Camera cannot define an upright horizontal view')
        right /= np.linalg.norm(right)
        forward = np.cross(np.array([0., 1., 0.]), right)
    forward /= np.linalg.norm(forward)
    up = np.array([0., 1., 0.])
    right = np.cross(forward, up)
    right /= np.linalg.norm(right)
    opencv_to_world = np.column_stack([right, -up, forward])
    three_to_world = opencv_to_world @ np.diag([1., -1., -1.])
    quaternion = Rotation.from_matrix(three_to_world).as_quat()
    if quaternion[3] < 0:
        quaternion *= -1
    return opencv_to_world, quaternion, forward

def virtual_rays(width=1200, height=1200, focal=600., cx=600., cy=600.):
    y, x = np.mgrid[:height, :width]
    return np.stack([(x + .5 - cx) / focal, (y + .5 - cy) / focal,
                     np.ones((height, width))], axis=-1)

def remap_coordinates(camera, world_to_original, world_from_virtual,
                      width=1200, height=1200):
    # Row-vector equivalent of R_original @ R_virtual_to_world @ ray_virtual.
    rays = virtual_rays(width, height, width / 2, width / 2, height / 2)
    original_rays = rays @ (world_to_original @ world_from_virtual).T
    lens = Fisheye(camera)
    xy, valid = lens.project(original_rays)
    valid &= (xy[..., 0] >= .5) & (xy[..., 0] <= camera['width'] - .5)
    valid &= (xy[..., 1] >= .5) & (xy[..., 1] <= camera['height'] - .5)
    # COLMAP uses half-pixel centers; OpenCV remap indexes centers at integers.
    return (xy[..., 0] - .5).astype(np.float32), (xy[..., 1] - .5).astype(np.float32), valid

def _node_transform(node):
    if 'matrix' in node:
        return np.asarray(node['matrix'], dtype=float).reshape(4, 4, order='F')
    result = np.eye(4)
    result[:3, :3] = Rotation.from_quat(node.get('rotation', [0, 0, 0, 1])).as_matrix() @ np.diag(node.get('scale', [1, 1, 1]))
    result[:3, 3] = node.get('translation', [0, 0, 0])
    return result

def bounds_from_glb(path):
    """Use actual GLB accessors plus every scene-node transform, including quantization TRS."""
    path = Path(path)
    with path.open('rb') as source:
        header = source.read(12)
        if len(header) != 12:
            raise ValueError('Truncated GLB')
        magic, version, length = struct.unpack('<III', header)
        if magic != 0x46546c67 or version != 2 or length != path.stat().st_size:
            raise ValueError('Expected complete glTF 2 binary')
        chunk_size, chunk_type = struct.unpack('<II', source.read(8))
        if chunk_type != 0x4e4f534a or chunk_size > length - 20:
            raise ValueError('GLB has no valid JSON chunk')
        gltf = json.loads(source.read(chunk_size))
    nodes = gltf.get('nodes', [])
    if not nodes:
        raise ValueError('Mesh has no scene nodes')
    child_nodes = {i for n in nodes for i in n.get('children', [])}
    if gltf.get('scenes'):
        roots = gltf['scenes'][gltf.get('scene', 0)].get('nodes', [])
    else:
        roots = [i for i in range(len(nodes)) if i not in child_nodes]
    corners = []
    def walk(index, parent, ancestry):
        if index in ancestry:
            raise ValueError('Cyclic GLB node graph')
        node = nodes[index]
        transform = parent @ _node_transform(node)
        if 'mesh' in node:
            for primitive in gltf['meshes'][node['mesh']]['primitives']:
                accessor = gltf['accessors'][primitive['attributes']['POSITION']]
                if 'min' not in accessor or 'max' not in accessor:
                    raise ValueError('POSITION accessor needs bounds; do not infer camera bounds from unrelated models')
                lo, hi = np.array(accessor['min'], float), np.array(accessor['max'], float)
                if accessor.get('normalized'):
                    component = accessor['componentType']
                    divisors = {5120: 127., 5121: 255., 5122: 32767., 5123: 65535.}
                    if component not in divisors:
                        raise ValueError('Unsupported normalized POSITION component type')
                    lo, hi = lo / divisors[component], hi / divisors[component]
                    if component in (5120, 5122):
                        lo, hi = np.maximum(lo, -1), np.maximum(hi, -1)
                for x in (lo[0], hi[0]):
                    for y in (lo[1], hi[1]):
                        for z in (lo[2], hi[2]):
                            point = transform @ np.array([x, y, z, 1.])
                            corners.append(point[:3] / point[3])
        for child in node.get('children', []):
            walk(child, transform, ancestry | {index})
    for index in roots:
        walk(index, np.eye(4), set())
    points = np.asarray(corners)
    if not len(points) or not np.isfinite(points).all():
        raise ValueError('Mesh has no finite geometry bounds')
    bounds = np.stack([points.min(axis=0), points.max(axis=0)])
    if not (bounds[0] < bounds[1]).all():
        raise ValueError('Mesh bounds are empty or flat')
    return bounds.tolist()

def frame_time(name, fps, first_index):
    match = re.search(r'(\d+)$', Path(name).stem)
    if not match:
        raise ValueError(f'Frame name has no numeric index: {name}')
    return (int(match[1]) - first_index) / fps

def source_mask(dataset, name):
    rel = Path(name)
    candidates = [dataset / 'masks' / rel.with_suffix('.png'),
                  dataset / 'masks' / Path(str(rel) + '.png')]
    for path in candidates:
        if path.is_file():
            mask = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
            if mask is None:
                raise ValueError(f'Cannot decode source mask: {path}')
            return mask, path
    raise FileNotFoundError(f'No original valid-pixel mask for {name}')

def choose_image(images, cameras, dataset, target, used, fps, first_index, lens):
    candidates = [im for im in images.values() if im['name'].replace('\\', '/').startswith(lens + '/') and im['id'] not in used]
    if not candidates:
        raise ValueError(f'No unused registered {lens} frame remains')
    candidates.sort(key=lambda im: abs(frame_time(im['name'], fps, first_index) - target))
    best = None
    for image in candidates[:12]:
        camera = cameras[image['camera_id']]
        r = qvec_to_rotmat(image['qvec'])
        virtual, quaternion, forward = upright_frame(r)
        mx, my, valid = remap_coordinates(camera, r, virtual, 64, 64)
        mask, mask_path = source_mask(dataset, image['name'])
        if mask.shape != (camera['height'], camera['width']):
            mask = cv2.resize(mask, (camera['width'], camera['height']), interpolation=cv2.INTER_NEAREST)
        sampled = cv2.remap(mask, mx, my, cv2.INTER_NEAREST, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
        fraction = float(np.mean(valid & (sampled > 127)))
        item = (image, camera, virtual, quaternion, forward, fraction, mask_path)
        if best is None or fraction > best[5]:
            best = item
        # Prefer the nearest actual registered time if its upright crop is clear.
        if fraction >= .85:
            return item
    if best[5] < .45:
        raise ValueError(f'No sufficiently valid upright photo near {target}s (best {best[5]:.1%})')
    return best

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, default=DEFAULT_RUN)
    parser.add_argument('--mesh', type=Path, help='Actual source/packed GLB in the same Y-up frame as the normalized poses')
    parser.add_argument('--output', type=Path, default=DEFAULT_OUT)
    parser.add_argument('--times', default='1,12,20,30,40,55')
    parser.add_argument('--fps', type=float, default=2.)
    parser.add_argument('--first-index', type=int, default=1)
    parser.add_argument('--lens', default='cam0')
    parser.add_argument('--overwrite', action='store_true')
    parser.add_argument('--self-test', action='store_true')
    args = parser.parse_args(argv)
    if args.self_test:
        return self_test()
    if args.mesh is None:
        parser.error('--mesh is required; placeholder scene bounds are forbidden')
    if args.output.exists() and not args.overwrite:
        raise FileExistsError(f'Output already exists: {args.output}')
    dataset = args.run / 'dataset'
    normalized = args.run / 'analysis/normalized-frame.json'
    if not normalized.is_file():
        raise FileNotFoundError('Run normalize_sfm.py first; source and mesh must share a confirmed Y-up frame')
    normalized_record = json.loads(normalized.read_text())
    if not normalized_record.get('coordinate_frame', '').startswith('+Y up'):
        raise ValueError('Normalized pose record does not declare +Y up')
    cameras, images, _ = read_model(dataset / 'sparse/0')
    bounds = bounds_from_glb(args.mesh)
    times = [float(t) for t in args.times.split(',')]
    if args.fps <= 0 or not np.isfinite(times).all():
        raise ValueError('Invalid frame rate or target times')
    output_photos = args.run / 'review/photos'
    output_photos.mkdir(parents=True, exist_ok=True)
    used = set();presets = [];details = []
    for number, target in enumerate(times):
        image, camera, virtual, quaternion, forward, _, mask_path = choose_image(images, cameras, dataset, target, used, args.fps, args.first_index, args.lens)
        used.add(image['id'])
        r = qvec_to_rotmat(image['qvec'])
        center = -r.T @ image['tvec']
        mx, my, valid = remap_coordinates(camera, r, virtual)
        source = cv2.imread(str(dataset / 'images' / image['name']), cv2.IMREAD_COLOR)
        if source is None or source.shape[:2] != (camera['height'], camera['width']):
            raise ValueError(f'Source frame is missing or its dimensions disagree: {image["name"]}')
        mask, _ = source_mask(dataset, image['name'])
        if mask.shape != source.shape[:2]:
            mask = cv2.resize(mask, (camera['width'], camera['height']), interpolation=cv2.INTER_NEAREST)
        photo = cv2.remap(source, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
        remapped_mask = cv2.remap(mask, mx, my, cv2.INTER_NEAREST, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
        valid &= remapped_mask > 127
        photo[~valid] = 0
        stem = f'osmo-upright-{number+1:02d}-{Path(image["name"]).stem}'
        photo_path, mask_output = output_photos / (stem + '.jpg'), output_photos / (stem + '-valid.png')
        if not args.overwrite and (photo_path.exists() or mask_output.exists()):
            raise FileExistsError(f'Reference image already exists: {photo_path}')
        if not cv2.imwrite(str(photo_path), photo, [cv2.IMWRITE_JPEG_QUALITY, 92]):
            raise IOError(f'Cannot save {photo_path}')
        cv2.imwrite(str(mask_output), valid.astype(np.uint8) * 255)
        actual_time = frame_time(image['name'], args.fps, args.first_index)
        preset = {'name': image['name'], 'label': f'Capture ~{actual_time:g}s · reprojected source',
                  'sourceFile': str(photo_path.resolve()), 'position': center.tolist(),
                  'quaternion': quaternion.tolist(), 'imageWidth': 1200, 'imageHeight': 1200,
                  'intrinsics': [600., 600., 600., 600.]}
        presets.append(preset)
        details.append({'source_image': image['name'], 'source_camera_id': image['camera_id'],
                        'target_time_approx_seconds': target, 'selected_time_approx_seconds': actual_time,
                        'valid_fraction': float(valid.mean()), 'source_mask': str(mask_path),
                        'output_valid_mask': str(mask_output), 'forward_world': forward.tolist(),
                        'opencv_virtual_to_world': virtual.tolist(),
                        'interpretation': 'Upright 90-degree rectilinear reprojection of an in-training masked source image; not holdout validation.'})
    if not presets:
        raise ValueError('No reference camera presets were generated')
    first = presets[0]
    forward = np.array(details[0]['forward_world'])
    result = {'bounds': bounds, 'startCamera': {'position': first['position'], 'quaternion': first['quaternion']},
              'homeTarget': (np.array(first['position']) + forward * 2).tolist(), 'presets': presets}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2))
    report = {'mesh': str(args.mesh.resolve()), 'normalized_poses': str(dataset / 'sparse/0'),
              'coordinate_frame': '+Y up; exactly the normalized SfM frame', 'bounds': bounds,
              'projection': 'Calibrated OPENCV_FISHEYE four-term polynomial from each registered COLMAP camera; source and virtual pose account for all roll/pitch.',
              'references': details, 'camera_metadata': str(args.output.resolve())}
    (args.run / 'analysis/web-camera-export.json').write_text(json.dumps(report, indent=2))
    print(json.dumps({'output': str(args.output), 'presets': len(presets), 'valid_fractions': [d['valid_fraction'] for d in details]}, indent=2))
    return 0

def self_test():
    camera = {'model': 'OPENCV_FISHEYE', 'width': 1920, 'height': 1920,
              'params': np.array([524.264, 524.165, 957.358, 955.318, .045868, .022023, -.0146743, .00140535])}
    angles = []
    for euler in ([0, 0, 0], [0, 90, 0], [0, 0, 90], [39, -53, 117], [179, 20, -33]):
        r = Rotation.from_euler('xyz', euler, degrees=True).as_matrix()
        virtual, q, forward = upright_frame(r)
        assert np.allclose(virtual.T @ virtual, np.eye(3), atol=1e-12)
        assert np.isclose(np.linalg.det(virtual), 1, atol=1e-12)
        three = Rotation.from_quat(q).as_matrix()
        assert np.allclose(three @ [0, 1, 0], [0, 1, 0], atol=1e-12)
        assert np.allclose(three @ [0, 0, -1], forward, atol=1e-12)
        assert abs(forward[1]) < 1e-12
        test = np.array([[0., 0., 1.], [.5, 0, 1], [0, -.5, 1], [-.7, .3, 1]])
        original = test @ (r @ virtual).T
        xy, valid = Fisheye(camera).project(original)
        rays, inverse_valid = Fisheye(camera).unproject(xy)
        mask = valid & inverse_valid
        expected = original / np.linalg.norm(original, axis=1)[:, None]
        if mask.any():
            angles.extend(np.linalg.norm(rays[mask] - expected[mask], axis=1).tolist())
            # Forward and inverse transforms recover the virtual ray exactly.
            recovered = rays[mask] @ (r @ virtual)
            target = test[mask] / np.linalg.norm(test[mask], axis=1)[:, None]
            assert np.max(np.linalg.norm(recovered - target, axis=1)) < 1e-6
    assert max(angles) < 1e-6
    upright_r = np.diag([1., -1., -1.])
    v, q, _ = upright_frame(upright_r)
    assert np.allclose(q, [0, 0, 0, 1], atol=1e-12)
    assert np.allclose(upright_r @ v, np.eye(3), atol=1e-12)
    print(json.dumps({'self_test': 'passed', 'pose_cases': 5,
                      'max_roundtrip_unit_ray_error': max(angles),
                      'three_camera_up_and_forward': 'passed',
                      'half_pixel_remap_convention': 'COLMAP 0.5 centers -> OpenCV zero-based centers'}))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
