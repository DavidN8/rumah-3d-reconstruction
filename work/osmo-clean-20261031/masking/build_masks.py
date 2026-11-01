"""Resumable per-frame SAM2/GroundingDINO masks for native dual fisheye frames.

All data is written under the specified new workspace/dataset. Source images,
old masks and model weights are read only. A final mask is an 8-bit binary PNG:
255 = eligible scene ray, 0 = ignored operator, reflection, or optical border.
No inpainting is used. Explicit mirror polygons cover *all* reflected content,
not merely people detected within it. Never imply that ignored scene is observed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import time

import cv2
import numpy as np
from PIL import Image, ImageDraw


HERE = Path(__file__).resolve().parent
DATA = Path('C:/Users/bombe/OneDrive/Documents/ChatGPT/Ruang Kamare/roomscan-reconstruction/data')
DEFAULT_DATASET = DATA / '20261031_OSMO360/clean-v3/dataset'
DEFAULT_RUNTIME = DATA / '20261019_095800/runtime/spirula'


def write_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.partial')
    temp.write_text(json.dumps(value, indent=2), encoding='utf-8')
    temp.replace(path)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def selected(args):
    value = json.loads(args.manifest.read_text(encoding='utf-8-sig'))
    if isinstance(value, list):
        records = value
    else:
        records = value.get('selected', value.get('selected_frames', value.get('frames')))
    if not records:
        raise ValueError('Manifest must contain nonempty selected/selected_frames/frames records')
    records = sorted(records, key=lambda r: r['source_frame'])
    for r in records:
        r.setdefault('filename', f"frame_{r['source_frame']:06d}.jpg")
        if Path(r['filename']).name != r['filename']:
            raise ValueError('Manifest filename must be a basename')
    for cam in args.cameras:
        for r in records:
            p = args.dataset / 'images' / cam / r['filename']
            if not p.is_file():
                raise FileNotFoundError(p)
            with Image.open(p) as im:
                if im.size != (3840, 3840):
                    raise ValueError(f'Expected native 3840 square: {p}: {im.size}')
    return records


def infer(args):
    records = selected(args)
    options = {
        'runtime': str(args.runtime.resolve()), 'text': args.text,
        'detector_threshold': args.detector_threshold, 'max_size': 0,
        'dilate_ratio': 0, 'mask_semantics': 'white_keep_black_exclude',
        'source': 'SAM2.1 small + GroundingDINO tiny, per image detection',
    }
    exe = args.runtime / 'bin/spirula.exe'
    for cam in args.cameras:
        raw_dir = args.work / 'operator-raw' / cam
        raw_dir.mkdir(parents=True, exist_ok=True)
        for start in range(0, len(records), args.chunk_size):
            chunk = records[start:start + args.chunk_size]
            # Split prefixes (eval_/train_) break chronological lexical order.
            # The CLI sorts basenames; remap precisely that order.
            ordered_chunk = sorted(chunk, key=lambda r: r['filename'])
            job = args.work / 'jobs' / cam / f'{start:05d}'
            inputs, outputs = job / 'images', job / 'masks'
            sources = []
            for r in chunk:
                source = args.dataset / 'images' / cam / r['filename']
                st = source.stat()
                sources.append({'filename': source.name, 'size': st.st_size,
                                'mtime_ns': st.st_mtime_ns})
            signature = digest({'options': options, 'sources': sources})
            done = job / 'done.json'
            if done.exists():
                prior = json.loads(done.read_text())
                if prior['signature'] != signature:
                    raise RuntimeError(f'Existing job configuration differs: {job}; use a new --work')
                if all((raw_dir / Path(r['filename']).with_suffix('.png')).exists() for r in chunk):
                    print(f'Resume: {cam} {start} already complete', flush=True)
                    continue
            inputs.mkdir(parents=True, exist_ok=True)
            outputs.mkdir(parents=True, exist_ok=True)
            for r in chunk:
                source = args.dataset / 'images' / cam / r['filename']
                link = inputs / source.name
                if not link.exists():
                    os.link(source, link)
            actual_inputs = sorted(p.name for p in inputs.glob('*.jpg'))
            if actual_inputs != [r['filename'] for r in ordered_chunk]:
                raise RuntimeError(f'Staging inputs mismatch; refusing mixed job: {job}')
            command = [str(exe), 'sam', 'track', '--model',
                       str(args.runtime / 'models/sam2.1_hiera_small_f16.ggml'),
                       '--detector', str(args.runtime / 'models/gdino-tiny.safetensors'),
                       '--frames', str(inputs), '--text', args.text,
                       '--detector-threshold', str(args.detector_threshold),
                       '--max-size', '0', '--detect-every', '1',
                       '--dilate-ratio', '0', '--remove-prompted',
                       '--device', args.device, '--out', str(outputs)]
            write_json(job / 'command.json', {'command': command, 'signature': signature})
            started = time.time()
            print(f'Infer {cam}: selected {start}..{start + len(chunk)-1}', flush=True)
            with (job / 'inference.log').open('w', encoding='utf-8') as log:
                completed = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT,
                                           check=False)
            if completed.returncode:
                raise RuntimeError(f'SAM failed ({completed.returncode}); inspect {job / "inference.log"}')
            mapped = []
            for j, r in enumerate(ordered_chunk):
                # CLI uses ordinal 0-based five-digit names, NOT input basenames.
                source_mask = outputs / f'frame_{j:05d}.png'
                mask = np.asarray(Image.open(source_mask).convert('L'))
                if mask.shape != (3840, 3840) or not np.isin(mask, [0, 255]).all():
                    raise ValueError(f'Invalid native binary mask: {source_mask}')
                dest = raw_dir / Path(r['filename']).with_suffix('.png')
                Image.fromarray(mask).save(dest)
                mapped.append({'input': r['filename'], 'source_frame': r['source_frame'],
                               'cli_output': source_mask.name, 'excluded_fraction': float((mask == 0).mean())})
            write_json(done, {'signature': signature, 'seconds': time.time() - started,
                             'options': options, 'mapping': mapped})
    print('All selected native frames have independent neural masks.', flush=True)


def optical_keep(shape, circle):
    h, w = shape
    cx, cy, radius = circle
    yy, xx = np.ogrid[:h, :w]
    return (xx - cx*w)**2 + (yy - cy*h)**2 <= (radius*min(w,h))**2


def polygon_mask(shape, polygons):
    h, w = shape
    out = np.zeros(shape, np.uint8)
    for polygon in polygons:
        xy = np.asarray(polygon, dtype=float)
        if xy.ndim != 2 or xy.shape[1] != 2 or len(xy) < 3 or not np.isfinite(xy).all():
            raise ValueError('Polygon must contain at least 3 finite normalized XY points')
        if xy.min() < 0 or xy.max() > 1:
            raise ValueError('Polygon must use normalized source-image coordinates')
        cv2.fillPoly(out, [np.round(xy * [w, h]).astype(np.int32)], 255)
    return out


def finalize(args):
    records = selected(args)
    if args.source_frames:
        records = [r for r in records if r['source_frame'] in args.source_frames]
    annotations = json.loads(args.annotations.read_text(encoding='utf-8-sig'))
    circles = annotations.get('optical_circle', {cam:[.5,.5,.485] for cam in args.cameras})
    reviewed = annotations['frames']
    audit_path = args.work / ('candidate-audit.json' if args.candidate else 'mask-audit.json')
    replaced = {(cam, r['source_frame']) for cam in args.cameras for r in records}
    rows = [r for r in json.loads(audit_path.read_text())['frames']
            if (r['camera'], r['source_frame']) not in replaced] if args.source_frames and audit_path.exists() else []
    for cam in args.cameras:
        final_dir = (args.work / 'candidate-final' if args.candidate else args.dataset / 'masks') / cam
        final_dir.mkdir(parents=True, exist_ok=True)
        for r in records:
            key = cam + '/' + r['filename']
            if key not in reviewed or (not args.candidate and not reviewed[key].get('reviewed')):
                raise ValueError(f'Visual review/mirror decision absent: {key}')
            raw_path = args.work / args.operator_layer / cam / Path(r['filename']).with_suffix('.png')
            mask = np.asarray(Image.open(raw_path).convert('L'))
            if mask.shape != (3840,3840):
                raise ValueError(f'Invalid raw dimensions: {raw_path}')
            remove = (mask < 128).astype(np.uint8)
            radius = args.dilation
            if radius:
                kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2*radius+1, 2*radius+1))
                remove = cv2.dilate(remove, kernel)
            review = reviewed[key]
            mirror = polygon_mask(mask.shape, review.get('mirror_polygons', []))
            manual = polygon_mask(mask.shape, review.get('extra_exclusion_polygons', []))
            if mirror.any():
                mirror = cv2.dilate(mirror, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (33,33)))
            keep = optical_keep(mask.shape, circles[cam]) & (remove == 0) & (mirror == 0) & (manual == 0)
            output = (keep.astype(np.uint8)*255)
            dest = final_dir / Path(r['filename']).with_suffix('.png')
            Image.fromarray(output).save(dest)
            row = {'camera':cam, **r, 'keep_fraction':float(keep.mean()),
                   'operator_fraction':float((remove != 0).mean()),
                   'mirror_fraction':float((mirror != 0).mean()),
                   'sha256':hashlib.sha256(dest.read_bytes()).hexdigest()}
            rows.append(row)
    write_json(args.work / ('candidate-audit.json' if args.candidate else 'mask-audit.json'), {
        'semantics':'255=keep; 0=excluded ray. Masked background is not automatically observed.',
        'shape':[3840,3840], 'operator_dilation_radius_px':args.dilation,
        'mirror_dilation_radius_px':16, 'optical_circle':circles,
        'review_annotations_sha256':hashlib.sha256(args.annotations.read_bytes()).hexdigest(),
        'frames':rows})
    print(f'Finalized and fingerprinted {len(rows)} native binary masks.', flush=True)


def sheets(args):
    records = selected(args)
    out = args.work / 'review'
    out.mkdir(parents=True, exist_ok=True)
    for cam in args.cameras:
        for start in range(0, len(records), args.sheet_count):
            chunk = records[start:start+args.sheet_count]
            tile, label_h, columns = args.tile, 32, 4
            canvas = Image.new('RGB', (columns*tile, math.ceil(len(chunk)/columns)*(tile+label_h)), '#24282e')
            draw = ImageDraw.Draw(canvas)
            for j,r in enumerate(chunk):
                p = args.dataset / 'images' / cam / r['filename']
                if args.use_thumbnails:
                    p = HERE.parent/'thumbnails'/cam/f"sample_{r['source_frame']//3+1:06d}.jpg"
                im = Image.open(p).convert('RGB').resize((tile,tile), Image.Resampling.LANCZOS)
                layer = args.dataset/'masks' if args.final else args.work/args.operator_layer
                mpath = layer / cam / Path(r['filename']).with_suffix('.png')
                if mpath.exists():
                    keep = np.asarray(Image.open(mpath).convert('L').resize((tile,tile), Image.Resampling.NEAREST))
                    pixels = np.asarray(im).copy()
                    remove = keep < 128
                    pixels[remove] = (pixels[remove]*.55 + np.array([255,15,50])*.45).astype(np.uint8)
                    im = Image.fromarray(pixels)
                else:
                    raise FileNotFoundError(f'Cannot generate a mask review from missing mask: {mpath}')
                x, y = (j%columns)*tile, (j//columns)*(tile+label_h)
                canvas.paste(im, (x,y+label_h))
                draw.text((x+5,y+4), f"{cam} n={r['source_frame']} t={r['time_seconds']:.2f}s", fill='white')
            tag='final' if args.final else args.operator_layer
            canvas.save(out/f'{tag}-{cam}-{start:04d}.jpg', quality=90)
    print(f'Review sheets: {out}', flush=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=['infer','finalize','sheets'])
    p.add_argument('--dataset', type=Path, default=DEFAULT_DATASET)
    p.add_argument('--manifest', type=Path, default=HERE.parent/'frame-selection.json')
    p.add_argument('--runtime', type=Path, default=DEFAULT_RUNTIME)
    p.add_argument('--work', type=Path, default=HERE)
    p.add_argument('--operator-layer', default='operator-raw')
    p.add_argument('--cameras', nargs='+', default=['cam0','cam1'])
    p.add_argument('--text', default='person;hand;arm;leg;shadow of a person')
    p.add_argument('--detector-threshold', type=float, default=.28)
    p.add_argument('--device', default='auto')
    p.add_argument('--chunk-size', type=int, default=24)
    p.add_argument('--dilation', type=int, default=32)
    p.add_argument('--annotations', type=Path, default=HERE/'review-annotations.json')
    p.add_argument('--sheet-count', type=int, default=16)
    p.add_argument('--tile', type=int, default=450)
    p.add_argument('--final', action='store_true')
    p.add_argument('--use-thumbnails', action='store_true')
    p.add_argument('--candidate', action='store_true', help='Write QA candidate masks in work only; cannot unlock reconstruction')
    p.add_argument('--source-frames', nargs='+', type=int, help='Re-finalize only these source frames, preserving prior audit rows')
    args = p.parse_args()
    if args.chunk_size < 1:
        p.error('chunk-size must be positive')
    {'infer':infer, 'finalize':finalize, 'sheets':sheets}[args.command](args)


if __name__ == '__main__':
    main()
