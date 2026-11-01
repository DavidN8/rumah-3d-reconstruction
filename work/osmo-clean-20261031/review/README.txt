OSMO NATIVE GAUSSIAN BASELINE AND PROVISIONAL WEBSITE
2026-10-31 — local review only; nothing deployed

Finding
The old v4 native Gaussian scene is substantially more complete at the six registered interior camera poses than the currently published triangle mesh. Native splats have continuous walls, ceiling, doors and furniture where the mesh has holes. This does NOT prove the old scene is geometrically accurate everywhere: the outside/orbit view exposes unobserved surfaces and floaters, and the six poses participated in geometry/training. The camera images are calibrated virtual pinhole crops from the original fisheye images, not an independent ground-truth capture.
Osmo covers the living/dining area and bathroom. The iPhone kitchen/bedroom capture is a different space; its apparent coverage is not an apples-to-apples camera comparison.

Artifacts
- renders/matched-pose-1.jpg through matched-pose-6.jpg: source / original native Gaussian / published mesh triptychs.
- renders/six-view-source-native-mesh.jpg: all six triptychs, 1800 x 4050.
- renders/native-pose-*.png, mesh-pose-*.png, compressed-pose-*.png, sog-pose-*.png: original 600 x 600 browser canvas saves.
- matched-review.json: exact pose/intrinsics and pixel metrics.
- native-v4.spz: 48,377,598 bytes; all 2,997,515 original SH0 splats retained.
- native-v4.spz.json: SHA256 and full decode round-trip checks.
- native-v4.sog: 36,835,837 bytes; all 2,997,515 original SH0 splats retained, mip metadata preserved.
- native-v4.sog.json: SHA256, official converter command, SOG members/count/model metadata.
- production/: isolated same-UI staging, not authorized for deployment.

Source model
data/20261031_OSMO360/recovery-v2/training/osmo-surface-v4/step-000050000.ckpt/splat.ply
203,831,437 bytes, binary little-endian, SH0, mip training primitive.
scene_transform.json is identity. Existing Y-up web camera positions/quaternions therefore apply directly; no speculative X rotation or world-axis flip was added.

Matched rendering
Three 0.180.0 + Spark 2.4.0, original PLY baseline at full splat count, no LoD, extSplats true, sortRadial false, blurAmount 0.3, preBlurAmount 0, no clipping or lighting. This is an actual Gaussian renderer, not the prior learned-color mesh atlas. It is not a bit-identical Spirula backend reference render.

Pixel measurements
Mean RGB RMSE against source at valid pixels: native 12.69, published mesh 26.83 (0–255 scale). SPZ 12.69. These are appearance diagnostics at training-geometry poses, not held-out reconstruction scores. The mesh photographic texture intentionally excluded these six photos, whereas native training did not; do not interpret RMSE alone as an unbiased algorithm ranking.
SPZ versus original PLY PSNR: 44.31, 45.62, 43.98, 44.09, 44.75, 44.09 dB. Native/SPZ images look nearly identical at these poses. Quantization is lossy, despite unchanged splat count.
SOG versus original PLY PSNR: 43.59, 44.71, 43.18, 43.25, 44.02, 43.31 dB. This saves 11.54 MB versus SPZ on this SH0 baseline. New SH2 size and appearance must be measured separately.

Packing
pack-spz.mjs uses official Adobe/Niantic @adobe/spz 0.2.3, SPZ v3, identity RUB coordinate convention. PLY quaternion wxyz is reordered into the SPZ API xyzw. Mip antialiased flag is retained. It deliberately supports only this audited SH0 PLY schema and rejects other layouts, so do not run it on the forthcoming SH2 checkpoint. Use an official general converter for SH2, then compare before/after at matched cameras.
Maximum position component round-trip error is 0.0001220703125 scene units. A large maximum log-scale error in the JSON is caused by SPZ's lower scale representable bound on almost-zero axes; it must not be reported as meters of geometric error. Pixel comparison above is the direct visual check for this baseline.
pack-sog.py uses official @playcanvas/splat-transform 3.10.3 in isolated converter/node_modules. Its temporary header-only copy adds `comment SplatRenderMode: mip` and preserves every original binary splat byte; original PLY is unchanged. `--gpu cpu` avoids GPU work (old SH0 conversion took 5.39 s); `--gpu 0` enables SH2 clustering when the GPU is available. SOG is supported by Spark 2.4.0 and six local renders were checked. The compression is lossy, and its file size alone does not prove a phone memory budget.

Native renderer/export audit
The retained Spirula runtime source is under:
C:/Users/bombe/OneDrive/Documents/ChatGPT/Ruang Kamare/roomscan-reconstruction/data/20261019_095800/runtime/spirula/source/src
app/Main.cpp has no render CLI subcommand in this 2026.10.16 build. Running `spirula render --help` entered the GUI; only that exact helper process was closed. No training was launched.
app/webviewer/Viewer.cpp exposes /render with a row-major 3x4 OpenGL c2w, fx/fy/cx/cy, width/height, camera_model and buffer_key. It returns JPEG display images. /buffers includes rgb, depth, alpha and depth_normal; median normals/depth appear only when enabled, distortion channels only when configured. /pick returns one ray-hit point, not a full numeric depth map. This HTTP interface is NOT a float depth/normal exporter. A backend extension or supported new exporter is required for quantitative depth/normal arrays; visual depth JPEG must not be treated as metric depth.

Production integration
Open http://127.0.0.1:53267/production/public/index.html after starting server.mjs from this review directory. The server binds only 127.0.0.1. Diagnostic page is http://127.0.0.1:53267/ .
The public landing page still contains exactly three choices: iPhone Fast, iPhone Full, Osmo. Choosing a radio or opening a quality deep link only preselects. Only Open model loads the viewer. Model switching/retry returns to chooser and requires another explicit Open. Native SPZ and Spark load only for Osmo. Both iPhone models retain their original files, cameras, loading behavior and geometry/texture limits. No existing website directory was modified.
Osmo starts inside at its own registered camera. Its Orbit transition preserves the current interior viewpoint rather than flying to the old mesh's exterior dollhouse camera. No ceiling or cabinet-height slicing is performed. Mesh-only Shading, See inside/back-face mode and Top view are hidden for native splats. Walk, orbit, touch movement, pinch, two-finger pan, camera presets and photographic comparison use the existing UI/control code.

Production limits and unfinished phone QA
Input size <=50,000,000 bytes, base source count <=3.1M splats, LoD displayed target 750k on phone / 2M desktop. No source points are dropped for file size. The current loader builds a LoD tree in a worker; this caps displayed detail but NOT transient decoder/LoD-tree memory. A prebuilt paged RAD can bound resident point pages, but its complete package size and network quota must be measured, not assumed. SOG is also supported by the native branch for future SH2 compression. Real Fold 7/iPhone 17 load/memory/touch testing is still unverified.

Browser verification, 2026-10-31
Local Chrome + RTX 5080, not phone hardware or mobile network:
- Staged old-native Osmo: ready in 6.13 s desktop, 6.82 s at 402 x 874 browser viewport; the narrower branch used 750k displayed LoD target and showed touch arrows.
- iPhone Fast: ready 0.27 s; iPhone Full: ready 2.46 s. These are local-host timings and do not predict cellular loading.
- Forward arrow press/release moved camera and activeMoves/keys were empty BEFORE cleanup.
- Server requests.jsonl proves initial HTML and radio selection fetched no model, metadata, photo, WebGL library or main viewer bundle. Open Osmo fetched SPZ + Spark. iPhone Fast/Full fetched GLB decoder chunks without requesting Spark/SPZ.
- Browser was returned to chooser, temporary viewport override reset and tab closed, releasing GPU resources before SfM/training.
- 21 focused choice/download/native-budget tests pass. Final bundle room-viewer-RZ2AJEEV.js was checked in Chrome: Walk-to-Orbit retained the exact camera position [0.36702162862946286, 1.541369844480851, -0.35076081614372406], and the interior remained visible. Test tab was returned to chooser and closed.
- production/browser-verification.json records scope, timings, request-log intervals and unverified physical-device limits.

Use with new clean reconstruction
1. Do not overwrite this old-baseline artifact or label it a rebuilt scene.
2. Export new native splats, pack SPZ/SOG without arbitrary source-count pruning, and record source SHA/count/SH degree/bytes.
3. Export new cameras and source crops in the same scene frame as the new checkpoint. Do not reuse these old poses. candidate.json accepts a fresh calibrated cameras path and optional worldFromTraining column-major 4x4 transform.
4. Update production/candidate.json, run node production/build.mjs, then repeat fixed-pose original-versus-compressed visual validation, quota checks and actual device QA.
5. Keep display preparation and download error timeouts. No silent fallback or automatic retry that spends additional mobile quota.

Deployment preparation
production/DEPLOY-NATIVE.txt is the operational checklist. prepare-deploy.py performs a local audit and, only for the exact approved fresh model/build, creates a new explicit archive and atomic deploy/rollback scripts. deploy-native.ps1 without -Execute makes no remote call; the execution path uses the existing scoped SSH/SFTP helper and Proxmox LXC 710. The current old/provisional baseline is blocked from final packaging. No actual deployment or server inspection was performed in this preparation task.
The retained expected release is 20261031-osmo-v3. Every replaced hardlink is detached before extraction, raw/gzip iPhone SHA and inode identity are checked, and failures after promotion restore the previous symlink only if no concurrent release replaced it. Public verification downloads no full models: HEAD checks and a bounded 12-byte fallback replace the old full-model verification GET. No nginx, authentication, DNS or Cloudflare settings change.
21 local deployment failure/fixture checks pass; generated deployment and rollback scripts pass bash -n, and PowerShell parsing/dry invocation pass. The current local audit covers 15 explicit assets, 3,515,221 bytes of lazy application code, preserved iPhone hashes, and zero remote calls. Existing 21 viewer tests also pass. The production JS bundle and manifest remain the same versions already browser-checked above.

Fresh camera and comparison tools
Use host-model-venv/Scripts/python.exe (scipy/cv2/numpy available) under data/20261019_095800/runtime.
export-clean-cameras.py requires --dataset <clean-v3/dataset>, --selection <clean-v3/analysis/frame-selection.json>, --normalization <work/osmo-clean-20261031/geometry/fresh-sfm-preparation-audit.json>, --output <fresh-web-cameras.json>. Default seven QA times are 1,12,20,25,40,52,60 seconds, explicitly covering the return bathroom visit; --split eval selects held-out training timestamps. It checks applied normalization, actual model SHA256, +Y up declaration and ray invariance. No old coordinate transform is reused. Selection timestamps and train/eval labels are recorded, with all registered source/image/camera IDs retained in a separate pose index. --self-test passes five ray/camera cases.
align-capture-frames.py requires --old-dataset <lite-v1/dataset>, --new-dataset <clean-v3/dataset>, --selection and --normalization as above, --output <alignment.json>, optionally --old-review-cameras <osmo-web-20261031-v3/osmo-cameras.json>. The old fps=2 output timestamp is not assumed to be its exact source exposure: nearby actual source images are compared first. One proper similarity is fitted by RANSAC to matched camera centers, with center and orientation residuals reported for all pairs. Matched old poses are exported in the new frame only if explicit coherence gates pass. Those poses are for evaluation, not production defaults or training. Synthetic 15-outlier rejection and inverse camera ray mapping pass (8.9e-16 error). The real alignment is pending fresh SfM.

Official documentation used
https://sparkjs.dev/docs/splat-mesh/
https://sparkjs.dev/docs/spark-renderer/
https://sparkjs.dev/docs/lod-getting-started/
https://developer.playcanvas.com/user-manual/splat-transform/
https://developer.playcanvas.com/user-manual/splat-transform/cli-reference/
https://developer.playcanvas.com/user-manual/gaussian-splatting/formats/sog/
https://registry.npmjs.org/@sparkjsdev/spark/2.4.0
https://registry.npmjs.org/@adobe/spz/0.2.3
