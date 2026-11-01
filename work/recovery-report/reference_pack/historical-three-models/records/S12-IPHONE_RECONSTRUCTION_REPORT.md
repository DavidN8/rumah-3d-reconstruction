# IPHONE WIDE-ANGLE RECONSTRUCTION REPORT
**Project:** `20261027_IPHONE_WIDE` — full-apartment reconstruction from a single iPhone walkthrough video
**Workspace:** `roomscan-reconstruction/data/20261027_IPHONE_WIDE/`
**Report:** `IPHONE_RECONSTRUCTION_REPORT.md` (this file, plain-text Markdown)
**Last updated:** 2026-10-27 07:10 — pipeline complete: unified SfM ✓, depth/normals ✓,
3 zones trained ✓, 8K meshes ✓, merged GLB ✓, viewer packaged ✓, Gate 2 PASS ✓

---

## 0. ISOLATION & PERFORMANCE POLICY (enforced across all scripts)

- Old Nikon Z8 scan `20261019_VID_2445`: **not touched** (frozen/archived).
- Old bedroom/bathroom scan `20261019_095800`: **read-only**; only its
  `runtime/host-model-venv` Python and `runtime/spirula/bin/spirula.exe`
  (2026.10.16, Vulkan) binaries/models are used.
- GPU throttles **removed**: no `CUDA_VISIBLE_DEVICES=-1`, no
  `SS_GPU_DUTY_CYCLE` / `GPU_DUTY_CYCLE` env (spirula's `GpuDutyCycle` pacing is
  unset => 100 % duty), no `gpu_memory_guard.py`, no `gpu-paused.json`,
  `OMP_NUM_THREADS` = all cores, Vulkan device `auto` (RTX 5080 16 GB).
- All pipeline scripts live in `20261027_IPHONE_WIDE/scripts/` and write only
  inside `20261027_IPHONE_WIDE/`.

## 1. SOURCE VIDEO (originals/IMG_0180.MOV)

| Property | Value |
|---|---|
| Device | iPhone 17 (iOS 26.5.1), main wide camera |
| Shot at | 2026-10-27 01:10 local (UTC+7), Jakarta |
| Codec | HEVC Main 10 (hvc1), Dolby Vision profile 8.4 base layer |
| Color | BT.2020 primaries, HLG transfer (`arib-std-b67`) |
| Coded size | 1920×1080 landscape, **display rotation −90°** ⇒ 1080×1920 portrait |
| Duration / frames | 156.9 s, 4705 frames @ 29.97 fps |
| Size | 250,980,749 bytes |

## 2. PHASE 1 — KEYFRAME EXTRACTION (done)

`scripts/01_extract_frames.py`:
- Single-pass ffmpeg decode with **HLG→sRGB tone-mapping** (`zscale` linear →
  `tonemap=mobius:peak=1000` → Rec.709/sRGB), auto-rotation applied ⇒
  portrait 1080×1920 JPG q95.
- Laplacian-variance sharpness measured on every decoded frame (downscaled
  grayscale); per window of 8 consecutive frames the single sharpest survivor
  is kept (~3.75 fps — the mandate's 3–4 fps target; an early 5-frame window /
  941-frame variant kept too many motion-blurred frames that broke the SfM
  chain and was replaced).
- **Result: 4705 decoded → 589 keyframes + 55 dense doorway frames (stride-4,
  src 1290–1510) = 634 keyframes**, decode ~35 s.
- Output: `frames/frame_%07d.jpg` (lexicographic = temporal order).

## 3. PHASE 2 — GPU SfM + LOOP CLOSURE (done — unified single-component model)

`scripts/02_run_sfm.py` — `spirula sfm auto` (Vulkan GPU features/matching,
CPU mapper threads = all cores). Iterations (all full-speed, no throttles):

| Attempt | Config | Result |
|---|---|---|
| 1 | SIFT, sequential-only pairs (19.8k pairs) | 26 % registered, 6 components |
| 2 | SIFT, retrieval+sequential+quadratic (442k ≈ exhaustive) | 60 % in main model, 4 components |
| 3 | ALIKED+LightGlue | LightGlue crashed (Vulkan GEMM bug); ALIKED+bruteforce: 9 components |
| 4 | Window-8 re-extraction (634 frames) + loosened seam tests | **2 components** (kitchen 176 / living 325), seam = one doorway |
| 5 | + dense doorway frames (stride-4, src 1290–1510) | 2 components, 501 images covered |
| 6 | flat mapper, `--max-models 1` | 302 only — growth cannot cross the doorway via PnP |

Final unification (`scripts/12_merge_models.py`): the two components stop 4
kept-frames (0.13 s) apart across the doorway; pairwise essential matrices are
degenerate (repetitive white walls → 135° rotation spread), so the join uses
**trajectory continuity**: junction pose equality (0.13 s apart ⇒ co-located),
scale from walking-speed continuity (0.0756/0.1142 ⇒ s = 0.6605), then ICP on
the full sparse clouds (5108 matches, **1139 points within 0.01 units**) and a
guard against the wrong-wall solution (blind 3D-3D Umeyama produced 0 tight
inliers versus 559 for the anchored solution — anchor wins).

**Final model: `colmap-gpu/merged/sparse/0` — 1 component, 501/634 frames
(79 %), all rooms locked in one rigid frame.** Camera steps across the former
seam are indistinguishable from normal walking (< 0.05 units). The 133
unregistered frames are motion-blurred/blank-wall shots (verified visually);
every room remains densely covered.

Camera: single shared **OPENCV** — fx≈874.8, fy≈874.0, cx≈540, cy≈964 at
1080×1920 (HFOV ≈ 63° ⇒ iPhone main wide camera), distortion ≈ 0 (k1 ≈ 1e-3).

### Gate 1 — trajectory & floorplan
- `analysis-merged/gate1-trajectory.json` + `analysis-merged/floorplan.png`
- Components: **1/1** ✓ — visually verified coherent room layout:
  kitchen (bottom-left) → living room (center) → corridor → bedroom (top-right),
  continuous color-ordered walk, no fold-backs, no scale jumps.
- Registration 79 % (< 90 % target): the shortfall is blurred/featureless
  frames, not fragmentation; see the note in the final report section.
- Reprojection (mapper): mean 0.61–0.71 px, median ≈ 0.45 px ✓ (the points3D
  `error` field is written as 0 by this spirula build; mapper log values used).

## 4. PHASE 3 — MoGe-2 DEPTH/NORMALS + DENSE SEEDS (done)

- `scripts/04_geometry.py`: built `zones/dataset-unified` (634 hardlinked
  frames + merged sparse model) and ran **`spirula geometry` with
  `moge2-vitl-normal.onnx` on the Vulkan GPU** (`--depth --max-size 1064
  --num-tokens 3600 --normal-format png`): 501 depth maps + 501 normal maps in
  **136 s** (≈3.7 maps/s).
- `scripts/05_seed_cloud.py`: MoGe depth maps robustly aligned per frame to the
  COLMAP sparse points (linear fit z = α·d + β, RANSAC; **469/501 frames
  aligned, median inlier fraction 0.98**), grid back-projection (every 2nd
  registered frame, every 4th pixel), ≥3-of-6 neighbour views agreeing within
  3 % depth, voxel dedup ⇒ **521,485-point seed cloud** in the unified frame.
- Zone seeds after split: zone-0 144,663 · zone-1 210,860 · zone-2 165,962
  (mandate target ~150–200k per zone ✓).

## 5. PHASE 4 — PER-ZONE TRAINING (running)

`scripts/06_zone_split.py`: zones from the floorplan-verified walk order with
nearest-camera point/seed ownership, all in the merged model's rigid frame:
- **zone-0 Kitchen** (src ≤ 1388)
- **zone-1 Living room + corridor** (1389–4090)
- **zone-2 Bedroom** (≥ 4091)

`scripts/07_train_zone.py` — `spirula train meshing` per zone with the proven
recipe + mandate settings: `--cap-max 2500000 --num-iterations 40000
--refine-stop-iter 30000 --train-resolution-divisor 1 --progressive-resolution 1
--progressive-resolution-full-at 0.3 --max-world-size <0.12 m calibrated>
--sh-degree 3 --sh-reg 0.001 --distraction-robustness mild
--floater-suppression mild --load-depths 1 --load-normals 1
--depth-supervision-weight 0.05 --normal-supervision-weight 0.02
--median-normal-supervision-weight 0.01 --scene-center none --train-frame
points` **plus frame-preservation flags** (`--orientation-method none
--center-method none --auto-scale-poses 0`) so every zone trains in the exact
same rigid world frame, and `--seed-pointcloud zones/<zone>/seed.ply`.

GPU: RTX 5080 at ~92 % utilization, ~5.7 GB VRAM, full duty cycle (no pacing) —
13.4 / 11.6 / 10.2 min per zone (40k iterations, 2.5M splats each, final
held-out PSNR 32–42 dB, SSIM 0.96–0.99). `scene_transform.json` verified
**identity** for every zone — all splats/meshes live in the merged model's one
rigid world frame.

### Mesh extraction (done)

`scripts/08_mesh_zone.py` — `spirula mesh` per zone with the proven recipe:
`--texture-size 8192 --carve-k 3 --merge-factor 0.5 --bisection-iters 4
--floater-min-faces 50 --fill-hole-ratio 0 --fill-hole-max-edges 64`.
Two deviations from the first attempt, both driven by the Gate-2 renders:
1. `--fill-hole-ratio 0` (proven recipe) instead of 0.25 — the 0.25 setting
   filled large loops with untextured triangles.
2. **`--iso 0.68`** — the default 0.5 isosurface meshed semi-transparent ghost
   splats (the swinging door and swaying curtain captured at different times),
   producing shard clouds around doorways; 0.68 keeps only dense cores.

Texture-preserving cleanup (`scripts/clean_room_mesh.py`, copied from the
published `scripts/video-scan/`): per-component detached-debris removal with
metre-scaled analysis thresholds (`--analysis-scale 0.2396`); positions, UVs
and texture bytes untouched, verified by SHA-256 after write. Removed: 3.1k /
4.0k / 1.9k debris triangles per zone; reports in `exports/zone-*/zone-*-clean.json`.

### Merge (done)

`scripts/09_merge_export.py`: the three cleaned zone GLBs merge with identity
transforms (shared world frame) into **`exports/iphone-full-room.glb`** —
11,641,867 triangles, 539 MB, three 8K atlases copied byte-verbatim and
re-verified by SHA-256, index bounds re-checked. Positions are scaled to
metres (x0.2396, calibrated from median camera height ≈1.5 m — approximate,
no metric reference exists in a video-only capture; relative geometry exact).
A wrapper node flips native Z-up to glTF Y-up; a wrapper-free
`iphone-full-room-native.glb` accompanies it for the render pipeline.
Merge report: `exports/merge-report.json`.

### Gate 2 — verification renders (done — PASS)

`scripts/render/raster_verify.py` + `scripts/11_gate2_verify.py`.
Blender Cycles (CPU/Embree) was installed and attempted, but its camera-model
bridge introduced convention errors for this portrait OPENCV capture, so the
final verification uses a **deterministic CPU z-buffer rasterizer** driven by
the exact calibrated projection the pipeline verified (K, R, t, distortion) —
cross-checked beforehand by projecting the model's sparse points onto source
frames (aligned, see `analysis/proj_frame_0004400.jpg`).

8 diagnostic views across kitchen, doorway, living room, corridor and bedroom
(`analysis/raytrace-check/*-sbs.jpg`, render vs source side by side):

| Metric | Result | Gate |
|---|---|---|
| Surface coverage per view | 1.000 (8/8 views) | mean ≥ 0.88 ✓ |
| Splat scale p90 | 0.0186 / 0.0244 / 0.0093 m (zone 0/1/2) | ≤ 0.06 ✓ |
| Recognizability | walls, cabinets, air fryer, doors, door frames, curtain, floor mats and shelf items all recognizable in renders | ✓ (soft/blurry in places — baked splat texture) |

Known artifacts, documented honestly: ghost surfaces remain around the two
transient objects (a door that swings and a curtain that sways during the
walk) — reduced, not eliminated, by `--iso 0.68`; one view (frame_0000206)
frames a nearby door instead of its shelf (small pose/framing offset).

## 6. VIEWER & DELIVERABLES (done)

- **Standalone viewer: `20261027_IPHONE_WIDE/review/index.html`** — vendored
  model-viewer + WASD walk/orbit controls (proven template), loads
  `models/iphone-full-room.glb` (the merged deliverable copy) with the
  verification gallery below. Serve with `python -m http.server 53250` from
  `review/` (HTTP required; all assets local/offline). All paths smoke-tested
  over HTTP (200).
- `exports/iphone-full-room.glb` — merged multi-mesh deliverable (539 MB).
- `exports/zone-*/zone-1_textured.glb` — per-zone 8K-textured meshes.
- `colmap-gpu/merged/sparse/0` — the unified COLMAP reconstruction (text).
- `analysis/` — gates, floorplan, verification renders, all stage logs.
- `scripts/01…11` — the complete reproducible pipeline for this capture.

## 7. FINAL STATUS

| Mandate gate | Result |
|---|---|
| Gate 1 — single unified component, floorplan coherent | **1 component, 501/634 frames (79 %)**, rooms locked in one rigid frame, seam verified seamless; below the 90 % target because 133 frames are motion-blurred/blank-wall shots (visually verified), not fragmentation |
| Gate 2 — coverage / scale p90 / recognizability | **PASS** — 1.000 coverage on all 8 views, scale p90 ≤ 2.4 cm |
| Isolation | `20261019_VID_2445` untouched; `20261019_095800` used read-only (venv + spirula binaries/models only) |
| GPU policy | no `CUDA_VISIBLE_DEVICES=-1`, no `SS_GPU_DUTY_CYCLE` (pacing off ⇒ 100 % duty), all CPU threads, GPU decode/features/matching/depth/training |
