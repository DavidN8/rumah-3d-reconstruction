"""Calibrated CPU native-fisheye <-> virtual-pinhole masks for SAM diagnostics.

These views are ONLY segmentation inputs; native RGB/calibration remains SfM's
input. Render output includes validity. Unwarp returns WHITE=EXCLUDED native
pixels, with zero outside the view's coverage. It never edits existing masks.
"""
from __future__ import annotations
import argparse
import json
import math
from pathlib import Path
import numpy as np
import cv2
from normalize_fresh_sfm import HERE, Fisheye, digest, save


def output_guard(path):
    path = path.resolve()
    if not path.is_relative_to(HERE):
        raise ValueError('Outputs must stay under the geometry helper directory')
    if path.exists():
        raise FileExistsError(f'Refusing overwrite: {path}')
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def camera_from_manifest(manifest, lens):
    row = json.loads(manifest.read_text())['cameras'][lens]
    if row['prefix'] != f'cam{lens}' or row['model'] != 'opencv-fisheye':
        raise ValueError('Expected original native OPENCV_FISHEYE calibration')
    return {'id': lens+1, 'model': 'OPENCV_FISHEYE', 'model_id': 5, 'width': 3840, 'height': 3840,
            'params': np.asarray(row['params'], dtype=float)}


def virtual_basis(theta_deg, phi_deg, roll_deg=0):
    """Columns map CV virtual rays to native CV rays; phi=0 right,90 bottom."""
    theta, phi, roll = np.deg2rad([theta_deg, phi_deg, roll_deg])
    forward = np.array([np.sin(theta)*np.cos(phi), np.sin(theta)*np.sin(phi), np.cos(theta)])
    reference_down = np.array([0., 1., 0.])
    right = np.cross(reference_down, forward)
    if np.linalg.norm(right) < 1e-8:
        right = np.cross(np.array([0., 0., 1.]), forward)
    right /= np.linalg.norm(right)
    down = np.cross(forward, right)
    # Positive roll rotates image axes in their plane; no reflection permitted.
    rr = np.cos(roll)*right + np.sin(roll)*down
    dd = -np.sin(roll)*right + np.cos(roll)*down
    basis = np.column_stack([rr, dd, forward])
    assert np.allclose(basis.T@basis, np.eye(3), atol=1e-10) and np.linalg.det(basis) > .999999
    return basis


def pinhole_map(camera, theta=75., phi=180., roll=0., fov=100., size=1024, max_native_theta=98.5):
    if not 0 < fov < 179 or not 0 <= theta < 180 or size < 16:
        raise ValueError('Invalid virtual view geometry')
    focal = size / (2*math.tan(math.radians(fov)/2))
    basis = virtual_basis(theta, phi, roll)
    y, x = np.mgrid[0:size, 0:size].astype(float)
    rays = np.stack([(x+.5-size/2)/focal, (y+.5-size/2)/focal, np.ones_like(x)], axis=-1)
    rays /= np.linalg.norm(rays, axis=-1, keepdims=True)
    native = rays@basis.T
    xy, valid = Fisheye(camera).project(native)
    angle = np.rad2deg(np.arctan2(np.linalg.norm(native[..., :2], axis=-1), native[..., 2]))
    valid &= angle <= max_native_theta
    valid &= (xy[..., 0] >= .5) & (xy[..., 0] <= camera['width']-.5)
    valid &= (xy[..., 1] >= .5) & (xy[..., 1] <= camera['height']-.5)
    mapx = (xy[..., 0]-.5).astype(np.float32); mapy = (xy[..., 1]-.5).astype(np.float32)
    mapx[~valid] = -1; mapy[~valid] = -1
    meta = {'camera': {**camera, 'params': np.asarray(camera['params']).tolist()},
            'view_size': size, 'focal': focal, 'principal_point': [size/2, size/2],
            'virtual_to_native_rotation': basis.tolist(),
            'center_theta_deg': theta, 'center_phi_deg': phi, 'roll_deg': roll,
            'horizontal_vertical_fov_deg': fov, 'max_native_theta_deg': max_native_theta,
            'pixel_convention': 'COLMAP/OpenCV calibrated centers at j+0.5; cv2.remap indices subtract 0.5',
            'purpose': 'Segmentation view only. No source images or SfM cameras are changed.'}
    return mapx, mapy, valid, meta


def unwarp_mask(mask, view_valid, meta, white_means='keep', rows_per_chunk=128):
    size = meta['view_size']
    if mask.shape != (size, size) or view_valid.shape != mask.shape:
        raise ValueError('SAM mask and validity must match the exact virtual view dimensions')
    camera = meta['camera']; model = Fisheye(camera)
    basis = np.asarray(meta['virtual_to_native_rotation'])
    focal = meta['focal']; cx, cy = meta['principal_point']
    excluded = mask < 128 if white_means == 'keep' else mask >= 128
    excluded &= view_valid > 127
    native_excluded = np.zeros((camera['height'], camera['width']), np.uint8)
    coverage = np.zeros_like(native_excluded)
    for start in range(0, camera['height'], rows_per_chunk):
        end = min(start+rows_per_chunk, camera['height'])
        yy, xx = np.mgrid[start:end, 0:camera['width']].astype(float)
        native, valid = model.unproject(np.stack([xx+.5, yy+.5], axis=-1))
        angle = np.rad2deg(np.arctan2(np.linalg.norm(native[..., :2], axis=-1), native[..., 2]))
        valid &= angle <= meta['max_native_theta_deg']
        local = native@basis
        valid &= local[..., 2] > 1e-8
        z = np.maximum(local[..., 2], 1e-8)
        u = (focal*local[..., 0]/z + cx - .5).astype(np.float32)
        v = (focal*local[..., 1]/z + cy - .5).astype(np.float32)
        valid &= (u >= -.5) & (u < size-.5) & (v >= -.5) & (v < size-.5)
        u[~valid] = -1; v[~valid] = -1
        sampled_valid = cv2.remap(view_valid, u, v, cv2.INTER_NEAREST, borderMode=cv2.BORDER_CONSTANT, borderValue=0) > 127
        sampled = cv2.remap(excluded.astype(np.uint8), u, v, cv2.INTER_NEAREST, borderMode=cv2.BORDER_CONSTANT, borderValue=0) > 0
        good = valid & sampled_valid
        native_excluded[start:end] = (good & sampled).astype(np.uint8)*255
        coverage[start:end] = good.astype(np.uint8)*255
    return native_excluded, coverage


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    render = sub.add_parser('render')
    render.add_argument('--image', type=Path, required=True)
    render.add_argument('--lens', type=int, choices=(0, 1), required=True)
    render.add_argument('--manifest', type=Path, default=HERE/'sfm-manifest-native3840.json')
    render.add_argument('--theta', type=float, default=75.)
    render.add_argument('--phi', type=float, default=180.)
    render.add_argument('--roll', type=float, default=0.)
    render.add_argument('--fov', type=float, default=100.)
    render.add_argument('--size', type=int, default=1024)
    render.add_argument('--native-valid-mask', type=Path)
    render.add_argument('--output-prefix', type=Path, required=True)
    inverse = sub.add_parser('unwarp')
    inverse.add_argument('--view-metadata', type=Path, required=True)
    inverse.add_argument('--mask', type=Path, required=True)
    inverse.add_argument('--white-means', choices=('keep', 'exclude'), required=True)
    inverse.add_argument('--output-prefix', type=Path, required=True)
    a = parser.parse_args()
    if a.command == 'render':
        image_path = a.image.resolve()
        rgb = cv2.imread(str(image_path), cv2.IMREAD_UNCHANGED)
        camera = camera_from_manifest(a.manifest, a.lens)
        if rgb is None or rgb.shape[:2] != (camera['height'], camera['width']):
            raise ValueError('Native 3840-square RGB source is required')
        mapx, mapy, valid, meta = pinhole_map(camera, a.theta, a.phi, a.roll, a.fov, a.size)
        if a.native_valid_mask:
            source_valid = cv2.imread(str(a.native_valid_mask), cv2.IMREAD_GRAYSCALE)
            if source_valid is None or source_valid.shape != rgb.shape[:2]:
                raise ValueError('Native validity mask size mismatch')
            valid &= cv2.remap(source_valid, mapx, mapy, cv2.INTER_NEAREST, borderMode=cv2.BORDER_CONSTANT, borderValue=0) > 127
        view = cv2.remap(rgb, mapx, mapy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
        view[~valid] = 0
        prefix = a.output_prefix.resolve()
        paths = [output_guard(Path(str(prefix)+s)) for s in ('.png', '.valid.png', '.json')]
        assert cv2.imwrite(str(paths[0]), view)
        assert cv2.imwrite(str(paths[1]), valid.astype(np.uint8)*255)
        meta.update(source_image=str(image_path), source_image_sha256=digest(image_path), lens=a.lens,
                    manifest_sha256=digest(a.manifest), view_image=str(paths[0]), view_validity=str(paths[1]),
                    valid_view_fraction=float(valid.mean()))
        save(paths[2], meta)
        print(json.dumps({'view': str(paths[0]), 'metadata': str(paths[2]), 'valid_view_fraction': meta['valid_view_fraction']}, indent=2))
    else:
        meta = json.loads(a.view_metadata.read_text())
        mask = cv2.imread(str(a.mask), cv2.IMREAD_GRAYSCALE)
        valid = cv2.imread(meta['view_validity'], cv2.IMREAD_GRAYSCALE)
        if mask is None or valid is None:
            raise ValueError('Mask and source view validity must exist')
        excluded, coverage = unwarp_mask(mask, valid, meta, a.white_means)
        prefix = a.output_prefix.resolve()
        paths = [output_guard(Path(str(prefix)+s)) for s in ('.excluded.png', '.coverage.png', '.json')]
        assert cv2.imwrite(str(paths[0]), excluded)
        assert cv2.imwrite(str(paths[1]), coverage)
        report = {'view_metadata': str(a.view_metadata.resolve()), 'mask': str(a.mask.resolve()), 'mask_sha256': digest(a.mask),
                  'input_white_means': a.white_means, 'output_white_means': 'excluded pixels',
                  'uncovered_pixels': 'zero; no opinion, never excluded', 'excluded_native_fraction': float((excluded>0).mean()),
                  'coverage_native_fraction': float((coverage>0).mean()),
                  'merge_rule': 'new_native_keep = existing_native_keep AND NOT(excluded_white); output is NOT a complete keep mask'}
        save(paths[2], report)
        print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
