# VID_2445 reconstruction: failure report and local handoff

Prepared on **2026-10-24, approximately 01:55–02:00 Asia/Bangkok (UTC+07:00)**.
This is a factual handoff for another AI session, not a successful reconstruction report.

The user explicitly requested this Markdown file in the local repository, **without committing it or adding it to `.gitignore`**. Writing this report does not authorize launching processing, publishing files, or changing security controls.

## 1. Read this first

**The current kitchen model failed the user's quality requirements.** It is a fragmented strip of countertop with substantial holes, jagged wall fragments, damaged object surfaces, and smeared detail. There is no accepted full-room reconstruction from the new Nikon recording.

- The source dataset contains **5,613 JPEG working frames at native 8K resolution**. They are present locally.
- The displayed model was trained from **only 84 consecutive source frames**, indices **2884–2967**, corresponding to **115.36–118.68 seconds** at 25 fps. That is roughly 3.3 seconds, or 1.5% of the source frame count.
- The 84 frames were split into **336 overlapping, native-pixel crops**. Those 336 training views are not 336 independent source frames and do not cover the complete video.
- The latest broader camera candidate contains **29 separate components**, with **4,463 unique frame positions across those components**. Its largest component contains **1,939 cameras**. These are candidate positions, not an accepted complete camera path.
- **1,150 source frames are absent from that candidate**, but their image files still exist. Do not conflate missing recovered positions with missing capture or deleted images.
- The kitchen run resumed at 22,000 steps and completed 24,000 steps. Its mesh contains **576,595 triangles, 435,493 vertices, and one embedded 8192 × 8192 texture**. These counts do not establish acceptable geometry or detail.
- The existing status file now explicitly says **`quality_rejected`**.
- No reconstruction processes matching this scan were found during the handoff checks. No training, meshing, feature matching, or other GPU compute was started while writing this report.
- **Important:** `runtime/gpu-paused.json` still contains `paused: false` from the last narrowly scoped GO. Idle processing is not the same as a persisted global pause. Do not run the restart helper just because that flag is false.

The user's latest reaction was that the result was unacceptable for the time and tokens spent. The previous assistant accepted responsibility: the local diagnostic was refined and packaged despite an unresolved full-room camera path and visibly poor surfaces. The next session should not report another iteration count as if it were a usable result.

## 2. Workspace and scope

Repository root:

```text
C:\Users\bombe\OneDrive\Documents\ChatGPT\Ruang Kamare
```

Current scan root, called **SCAN** below:

```text
C:\Users\bombe\OneDrive\Documents\ChatGPT\Ruang Kamare\roomscan-reconstruction\data\20261019_VID_2445
```

Older scan root, called **OLD** below:

```text
C:\Users\bombe\OneDrive\Documents\ChatGPT\Ruang Kamare\roomscan-reconstruction\data\20261019_095800
```

Paths beginning with `analysis/`, `runtime/`, `review/`, `training/`, `tracking-all/`, `dataset-`, `geometry-guidance-001/`, `exports-`, or `originals/` in this report are relative to **SCAN**, unless explicitly stated otherwise.

At the time of checking:

| Repository item | Observed value |
| --- | --- |
| Branch | `claude/nice-meitner-x6oy11` |
| HEAD | `91e8450` — `Consolidate Drive models into one download and simplify setup` |
| Initial tracked working-tree changes | None reported by `git status --short` |
| Local reconstruction data | Already ignored by repository rules under `roomscan-reconstruction/data/` |
| This report | Intended to remain a visible, untracked Markdown file at the repository root |

The root `CLAUDE.md` primarily describes the **older bedroom/bathroom release** and its public model download workflow. Read it for repository conventions, but do not mistake that release for a successful reconstruction of `VID_2445`. Do not change branches, reset the repository, or overwrite other-session changes to make this handoff easier.

## 3. What the user actually wants

The intended deliverable is a high-quality, detailed room reconstruction with useful polygon geometry and textures, inspectable in a browser. The kitchen needs recognizable, coherent surfaces and object detail. A photogenic view or a large texture alone is insufficient.

Earlier work concerned a bedroom and bathroom from `20261019_095800.mp4`, including a moving bathroom door and changes in lighting. The user suggested excluding the transition or reconstructing rooms separately and aligning them at the doorway. That older capture and its existing exports are separate from the current Nikon scan.

For the newer Nikon Z8 recording, the user explicitly chose to continue with the existing footage. They said it is sharp and workable despite high-ISO color/noise. They repeatedly disputed the claim that they had failed to capture the kitchen and said they made several passes. **There is no verified basis in this handoff for blaming missing capture coverage.**

The user supplied these appearance references. They are references to the desired result, not evidence that any particular method in this repository reproduces those results:

- <https://www.reddit.com/r/GaussianSplatting/comments/1wmlobx/scanning_houses_just_got_10x_cheaper/>
- <https://www.reddit.com/r/GaussianSplatting/comments/1vyvyv4/gaussian_splat_from_eyes_wide_shut_from_x/>

Persistent requirements and preferences:

- Keep every developed 8K working frame and preserve the original recording.
- The user authorized high-quality compressed 8K working copies instead of approximately terabyte-scale uncompressed images.
- Do not silently downscale RGB images or substitute a sparse frame sample for the requested complete reconstruction.
- Native-pixel tiling can preserve detail within selected frames, but it must not be described as using all video frames.
- Keep detailed geometry and textures. Do not disguise gaps by aggressive global decimation, texture reduction, or invented surface repair presented as measured geometry.
- Use a dark viewer background, intuitive navigation, WASD movement, Q/E height, gentle scrolling, and source-frame comparison.
- The user dislikes clutter: one current downloadable model package, no proliferation of ZIPs or cleanup reports in Drive. This Markdown handoff is specifically requested locally.
- GPU availability changes when the user games or shuts down. Respect the latest instruction rather than treating an earlier GO as indefinite availability.
- Preserve the strict GPU-memory limit described below. Brief compute spikes were explicitly permitted later; memory spikes above 80% were not.

The older release has a public Drive package and GitHub setup documentation. The current task is local documentation; no new capture or failed kitchen model was published as part of this handoff.

## 4. Source data: what exists and what was used

### Original files and developed frames

Current on-disk checks:

| Item | Location | Observed state |
| --- | --- | --- |
| Nikon RAW recording | `originals/VID_2445.NEV` | Present, 81,030,462,976 bytes |
| Companion MP4 | `originals/VID_2445.MP4` | Present, 660,313,222 bytes |
| Developed RGB frames | `dataset-all-8k/images/f_000000.jpg` through `f_005612.jpg` | 5,613 matching JPEG files counted |
| Development record | `dataset-all-8k/development-status.json` | `complete`, 5,613 / 5,613, format `jpeg100` |
| Sample native image | `dataset-all-8k/images/f_002928.jpg` | Header checked: 8256 × 4644, RGB |

The dataset records and previous preparation identify these as developed RAW working images. The handoff checks did not re-decode the RAW recording or hash all 81 GB. The source files were not modified during this audit.

Do not use the smaller companion/proxy video as an unnoticed replacement for the developed 8K RGB data. Tracking data, auxiliary geometry maps, preview thumbnails, and original RGB frames have different roles and resolutions.

### Local model dataset

The failed local model uses:

```text
dataset-native-camera-kitchen-034/
tracking-all/native-reserved-global-026/models/0/
```

Important records:

- `dataset-native-camera-kitchen-034/geometry-plan.json`
- `dataset-native-camera-kitchen-034/ready.json`
- `dataset-native-camera-kitchen-034/tiles-index.json`
- `dataset-native-camera-kitchen-034/training-command.json`
- `tracking-all/native-reserved-global-026/solver-comparison.json`

The geometry plan records 84 source poses, four crop-camera intrinsics, 336 tile views, and **2,750 sparse points**. The four crop boxes cover the selected 8256 × 4644 images with overlap. The preparation code checks crop/source consistency and reports no RGB resampling. Auxiliary depth/normal guidance is recorded at **1064 × 598**, and is cropped for the tile views; it is not native 8K measured depth.

The preparation code requires reserved-photo checks for the local camera solution: sufficient checks, at least 500 held-out observations, median at most 2 pixels and p90 at most 4 pixels. Passing that gate did **not** produce an acceptable surface reconstruction. These checks must not be promoted into proof of a correct whole-room model.

Some fields in `geometry-plan.json` describe the planning stage and remain `images_materialized: false` / `ready_for_training: false`. Consult the later `ready.json`, tile index, and actual files before interpreting those fields. Likewise, 336 tiles derived from 84 frames do not create independent camera coverage.

## 5. Latest training and mesh export

### Saved artifacts

| Artifact | Path |
| --- | --- |
| Latest saved training checkpoint | `training/native-camera-kitchen-034/step-000024000.ckpt/` |
| Optimizer/training state | `training/native-camera-kitchen-034/step-000024000.ckpt/state.tar` |
| Gaussian representation | `training/native-camera-kitchen-034/step-000024000.ckpt/splat.ply` |
| Effective training settings | `training/native-camera-kitchen-034/config.json` |
| Training scene transform | `training/native-camera-kitchen-034/scene_transform.json` |
| Raw mesh export | `exports-native-camera-kitchen-034/native-camera-kitchen.glb` |
| Upright display wrapper | `exports-native-camera-kitchen-034/native-camera-kitchen-preview.glb` |
| Training log | `logs/native-camera-kitchen-train.log` |
| Mesh log | `logs/native-camera-kitchen-mesh.log` |
| Authoritative local quality record | `analysis/native-camera-kitchen-status.json` |

The 22,000-step checkpoint was the resume source. The run saved only the latest checkpoint, and only `step-000024000.ckpt` was present in the inspected training directory. Do not assume the older checkpoint still exists.

### Observed settings and completion

- Resumed from 22,000 to **24,000 steps**, adding 2,000 steps in **2 minutes 43.946 seconds** according to the log. This is the time for that local continuation, not the total project cost or a full-room estimate.
- **600,000 splat cap**, with 600,000 splats reported at completion.
- Native RGB training divisor **1**, progressive resolution disabled, disk image cache, maximum training batch size 1, split batch enabled.
- Camera optimization disabled for this training run.
- Depth and normal guidance enabled; source initialization uses the sparse points.
- Configuration records `eval_mode: all`, `validation_fraction: 0`, and saved evaluation images enabled. No independent surface-quality acceptance follows from that configuration. No evaluation images were found in the inspected checkpoint directory; do not imply otherwise from the flag alone.
- Refinement stop is recorded at 14,000 steps. The last training lines show `num_added=0`. The final continuation should not be described as adding coverage or new camera views.
- The last logged values include PSNR 28.41 and SSIM 0.474. These are training-log quantities, not verified whole-room or held-out mesh scores.
- Meshing completed in approximately **97.42 seconds**, exporting 435,493 vertices and 576,595 faces, then baking an 8192 × 8192 texture.

The controller's mesh settings include `merge-factor 0.5`, `bisection-iters 4`, `floater-min-faces 50`, `fill-hole-ratio 0`, `fill-hole-max-edges 8`, and `carve-k 8`. Those are recorded implementation choices, **not validated optimal settings**. Do not assume that raising hole filling would recover faithful missing geometry.

### Artifact fingerprints verified for this handoff

| File | Bytes | SHA-256 |
| --- | ---: | --- |
| `exports-native-camera-kitchen-034/native-camera-kitchen.glb` | 41,979,020 | `fc123e86a9160448ebfb0f2af69a11c49385b690390546a80cb68afb341045d5` |
| `exports-native-camera-kitchen-034/native-camera-kitchen-preview.glb` | 41,979,280 | `b87af5856cee095e42100c3a55e981d81e242827a013c05c29f7c2b638220f5a` |
| `review/Kitchen-preview.html` | 61,023,596 | `bdec529e558aaac6cd5421ba1ebb52e46b8553a448a32d423c870d6dafe09a51` |
| `runtime/package_native_kitchen_html.py` | 16,502 | `874397b20705546f83e8cdbf760b0cf5685cf0469a92b4eff54e08f813720bdf` |

Earlier packaging verified that the preview GLB changes the root display orientation while preserving the original binary geometry/texture payload. Its full-file hash therefore differs from the raw export. Display copies of source frames are rotated 90 degrees counterclockwise from the native sideways images; do not apply a second rotation to source camera geometry without checking the existing conversion.

## 6. Visual rejection and limits of the diagnosis

### Directly observed

The user's browser screenshot shows a narrow countertop strip surrounded by torn wall fragments. Rice cookers, bottles, dishes and the sink area are recognizable, but the surfaces contain substantial missing triangles, jagged silhouettes and texture smearing. It is not an acceptable detailed room model.

The same types of defects are already visible in:

```text
review/Kitchen-preview.jpg
```

That saved comparison shows source images and CPU mesh renders around 116.16, 117.12 and 117.92 seconds. The source images visibly contain surfaces where the reconstruction is broken. The problem existed before the browser loaded the asset; fixing browser loading did not fix geometry.

On **2026-10-23T18:46:26Z**, `analysis/native-camera-kitchen-status.json` was changed to:

```json
{
  "status": "quality_rejected",
  "local_surface_quality_verified": false,
  "whole_room_complete": false
}
```

The file also records the user screenshot and saved source/model comparison as the review basis. Its earlier `updated_utc` is the export timestamp; `quality_reviewed_utc` is the later quality decision. The saved PID 33048 is historical, not evidence of an active worker.

### Confirmed workflow failures

1. The intended full-room camera recovery is unresolved. Training a small, contiguous subset cannot produce the requested room coverage.
2. Local camera-check success and training/export completion were treated as progress despite a failed visual result.
3. Packaging and viewer work continued after the saved comparisons already showed severe mesh defects.
4. Texture size, triangle count and training steps were given more prominence than coherent surfaces and source-image agreement.
5. All images being developed was not the same as all images being registered or used in training. Future reporting must keep these counts separate.

### Still unknown; do not present these as established causes

- How much damage originates in the local camera/depth geometry, Gaussian training, versus extraction of a polygon mesh from that representation.
- Whether the trained Gaussian checkpoint renders substantially better than its extracted mesh from the same cameras. A controlled comparison has not been established by this audit.
- Whether auxiliary depth/normal priors, their scale/crop conventions, or regularization are contributing to the defects.
- Whether local parallax and triangulation support are sufficient for reliable depth despite passing the reserved correspondence gate.
- Which lens/calibration, matching or component-connection changes would yield an accepted complete camera solution.
- Whether the existing footage can ultimately reach the user's requested quality with a corrected pipeline. Neither success nor capture inadequacy has been demonstrated.

There is **no validated fix and no defensible full-room completion estimate** at this handoff. Do not promise that simply adding iterations, triangles, splats or hole filling will solve it.

## 7. Broader camera recovery and preserved intermediate work

The latest inspected broader candidate is:

```text
tracking-all/learned-connected-room-039/
```

Relevant files:

- `analysis/learned-connected-room-solve-status.json`
- `tracking-all/learned-connected-room-039/assessment.json`
- `tracking-all/learned-connected-room-039/models-on-disk.json`
- `tracking-all/learned-connected-room-039/camera-support-audit.json`
- `tracking-all/learned-connected-room-039/native-holdout-validation.json`
- `tracking-all/learned-connected-room-039/learned-connection-validation.json`
- `tracking-all/learned-connected-room-039/models/`
- `logs/learned-connected-room-039.log`

Observed status: `awaiting_independent_validation`, stage `camera_candidate_ready`, `full_room_quality_verified: false`.

| Camera candidate measure | Observed value |
| --- | ---: |
| Components | 29 |
| Unique candidate frame positions | 4,463 |
| Source frames absent from the candidate | 1,150 |
| Largest component | 1,939 cameras |
| Cameras with support flags in the audit | 1,425 |

The current assessment's component overlapping the 84-frame kitchen test is model 8, with 89 cameras and 3,551 points. **That component is not the same model used for the failed 034 training**, which used `native-reserved-global-026/models/0`. Numeric component IDs have been remapped in some records. Use complete paths and recorded fingerprints, not a bare component number.

The support audit flags weak image-area coverage, limited triangulated observations, limited baseline support, large fitted errors, and invalid/nonpositive projections. These are diagnostic flags, not a substitute for visual correspondence checking.

The native holdout file reports 794 checked pairs, 77,106 held-out matches and 556 frames with unused-match checks. It explicitly warns that unused SIFT matches can still pair unrelated edges. Its unscreened pair statistics alone establish neither an accepted camera solution nor a definitive camera error. It also explicitly states that appearance validation is required and full-room quality is unverified.

Other retained work:

| Stage | Record | Last saved state |
| --- | --- | --- |
| Native 8K CPU matching | `analysis/full8k-cpu-matches-status.json` | Paused; 8,639 / 11,221 pairs processed, 6,664 verified pairs; last saved snapshot |
| Native feature/match database | `tracking-all/raw-colmap-sift-cpu-001/database.db` | Preserved; do not overwrite or delete |
| Auxiliary geometry generation | `analysis/geometry-guidance-status.json` | Complete: 5,613 / 5,613 frames |
| Guidance outputs/index | `geometry-guidance-001/` | Auxiliary maps, not a completed reconstruction |

The matching status contains an old estimated remaining time. It is a snapshot from an earlier run and should not be quoted as a current full-room ETA. Many older experiments exist under `tracking-all/`, `analysis/`, `dataset-*` and `training/`; existence does not imply acceptance. Avoid blindly resuming every file named `continue_*`.

## 8. Preview state and the other session's fixes

Primary offline preview:

```text
SCAN\review\Kitchen-preview.html
```

Related implementation:

| File | Role |
| --- | --- |
| `runtime/package_native_kitchen_html.py` | Builds the self-contained HTML; edit this for durable packaging changes |
| `runtime/prepare_native_kitchen_preview.py` | Creates display-oriented GLB metadata and recorded views |
| `review/mesh-viewer.html` | Viewer template |
| `review/mesh-controls.js` | Navigation implementation |
| `review/vendor/model-viewer.min.js` | Bundled viewer dependency |
| `review/detail-models.json` | Model metadata and local camera views |
| `review/native-kitchen-reference/` | Five rotated/downscaled display reference photos; original images are separate |
| `review/kitchen-detail.html` | Old entry page now redirects to the standalone preview |
| `review/index.html` | Progress page with an always-available saved-preview link and an offline branch |
| `runtime/serve_scan.py` | Older loopback progress/asset server; not required for the standalone file |
| `runtime/preview-entry-backup-20261024/` | Earlier entry/template-generator backups; these are not the newest fixes |

The old page failed because it fetched `/status.json` and other files before it could open the model. It required a server and failed when opened offline or when the endpoint was unavailable.

The first standalone build removed server dependencies but still had a CSP/WebAssembly initialization issue. Another AI session subsequently changed the generator. **Preserve those newer changes.** Current code inspection confirms:

- `wasm-unsafe-eval` is allowed specifically for the bundled decoder's WebAssembly initialization; general JavaScript `unsafe-eval` and HTTP connections are not enabled.
- Model data is decoded in bounded chunks and yields between chunks, reducing temporary memory pressure and page freezing.
- GLB structure, embedded asset requirements, triangle count, PNG texture size and model hash are checked before packaging.
- Specific loading, CSP, WebGL/context-loss and error-detail handling is present.
- Controls remain disabled until ready, and the header height is handled dynamically.
- The output is written through a temporary file to avoid leaving a partial replacement.
- The saved source/model comparison is embedded as a fallback while loading or after failure.

The user subsequently supplied a screenshot showing the new standalone preview **rendering the kitchen model**. This is evidence that it rendered in their browser. It is not comprehensive verification of WASD, all controls, downloads, source comparison, or every browser. The previous assistant's automated browser test remained unavailable.

Some UI metadata still describes this as an inspection preview with remaining holes. The authoritative quality decision is now **rejected**. Do not treat the older wording as acceptance, and do not erase the other session's viewer fixes by restoring an earlier generator.

## 9. Policy errors: facts and boundaries

Two separate tool failures occurred:

1. A normal background launch of the existing local preview server was rejected before process creation with **`blocked by policy`**. No detailed rationale was returned.
2. Browser automation rejected a `file:` URL, explicitly permitting only HTTP/HTTPS and explicitly prohibiting workaround access through alternate browser surfaces or indirect execution.

The session already reported full filesystem access and a `never` approval mode, so it was not established that changing ordinary filesystem permissions would solve either rejection. The server rejection's deeper cause remains unknown. Do not invent a cause such as antivirus, OneDrive, a specific operating-system restriction, or an organizational rule.

The earlier agent did not remove these controls. It prepared a materially different deliverable: one offline HTML artifact that does not require the denied server launch. The user can inspect their artifact in their own browser, as their later screenshot demonstrates.

Do not attempt the denied actions through a different shell, hidden helper, browser backend, raw browser-control channel, or another agent to bypass the restriction. Use supported permission diagnostics and explicit approval mechanisms if available in a future environment. If unavailable, state the limitation accurately.

Official documentation consulted during the earlier investigation:

- [Sandboxing and permissions](https://learn.chatgpt.com/docs/sandboxing)
- [Automatic approval review](https://learn.chatgpt.com/docs/sandboxing/auto-review)

These tool restrictions explain limits on automated server/browser testing. **They do not explain or excuse the poor reconstructed mesh.**

## 10. GPU limits, process ownership and restart hazards

The user has experienced several crashes/restarts and repeatedly stopped processing to game. Their latest explicit resource rule allows brief compute spikes while requiring **GPU memory below 80%**.

Inspect these before any authorized future processing:

```text
runtime/gpu-memory-policy.json
runtime/gpu_memory_guard.py
runtime/gpu_worker_config.py
runtime/gpu-paced-build.json
runtime/gpu-paused.json
analysis/gpu-memory-status.json
logs/gpu-memory-samples.jsonl
```

Current saved policy:

| Setting | Value |
| --- | --- |
| GPU | RTX 5080 |
| Maximum total GPU memory | 80% |
| Guard stop threshold | 75%, preserving five percentage points of margin |
| Memory polling | 0.1 seconds |
| Native submission duty fraction | 0.5 |
| Submission budget | 10 ms |
| Compute mode | Bounded transients |
| Compute average window | 10 seconds |
| Compute stop average | 75% |
| Maximum continuous compute burst at/above 80% | 5 seconds |

This is process-local pacing and sampled monitoring, **not a driver-enforced memory partition or an absolute hardware guarantee**. Total GPU memory includes other applications. Do not substitute an unpaced executable, remove the watchdog, or weaken the limits to get a run through.

The worker selector checks the paced binary's recorded SHA-256, permitted location and hold flag. The guided runner also preserves a **100 GiB free-disk reserve** and holds process-owned locks. Stop only the verified job owned by this task, not arbitrary Python/GPU/browser/game processes.

For the latest completed local run, saved telemetry reports a peak total memory use of approximately **31.33% during training** and **25.96% during meshing**. The last memory status says `finished` and `child_running: false`; it is historical telemetry, not a live reading.

### Specific restart hazards found during this handoff

1. `runtime/gpu-paused.json` says `paused: false` with the reason that the user authorized resuming 22,000 steps and exporting the preview. That specific work is complete. The flag must not be used as evidence of a current request to start more work.
2. `runtime/resume_after_restart.ps1` is a broad dispatcher for multiple companion jobs. It is not a harmless preview opener. Read its selected states and workers before invoking it. The rejected kitchen status is not in its companion-job auto-resume allowlist, but other saved statuses may select other jobs.
3. **`runtime/continue_native_camera_kitchen.py` has a quality-state bug:** if `exports-native-camera-kitchen-034/native-camera-kitchen.glb` exists, it immediately writes `awaiting_quality_review` and returns. Calling it can overwrite the new `quality_rejected` decision without changing or improving the model. Preserve the rejection before any future reuse of that controller. This report documents the defect; it does not claim to have fixed the controller.
4. Saved status files retain historical PIDs, and lock files can remain after jobs exit. Verify the live process, command line and ownership before concluding a job is active or stopping it. A stale PID alone is not sufficient.

## 11. Existing runtime locations

An already-working Python interpreter is available at:

```text
C:\Users\bombe\OneDrive\Documents\ChatGPT\Ruang Kamare\roomscan-reconstruction\data\20261019_095800\runtime\host-model-venv\Scripts\python.exe
```

The newer scan intentionally reuses a runtime under the older scan folder. Do not delete OLD as an apparent obsolete capture without checking this dependency.

Useful existing components:

- `runtime/colmap-python/` — local CPU PyCOLMAP support.
- `runtime/continue_native_camera_kitchen.py` — local 034 training/mesh controller; see the quality-state bug above.
- `runtime/prepare_native_camera_kitchen.py` — local camera checks, native crop preparation and guidance crop consistency.
- `runtime/run_guided_kitchen.py` — shared process supervision, pacing, memory guard and disk reserve.
- `runtime/render_kitchen_mesh_check.py` — existing mesh comparison renderer. Inspect its arguments and cost before running it; saved comparisons already exist.
- `runtime/continue_learned_room_solve.py` — broader 039 camera candidate controller.
- `runtime/continue_full8k_cpu_matches.py` — remaining native matching work.
- `runtime/continue_geometry_guidance.py` — auxiliary map generation, already complete for all frames according to the saved status.

Many libraries and older experiments live under `runtime/`. Search specific top-level scripts and records before recursively printing package source trees. Do not install another environment or rebuild a GPU binary merely because a fresh AI session lacks the previous context.

## 12. Recommended next investigation, without an automatic new run

This is a proposed investigation order, not evidence that any remedy has succeeded and not an instruction to start compute while the user is unavailable.

1. **Read the current rejection and preserve the evidence.** Verify the latest user resource instruction and active processes. Keep the RAW recording, all 5,613 JPEGs, databases, candidate camera models, checkpoint, GLBs and other-session viewer fixes.
2. **Separate the three technical questions:** whether camera/depth geometry is correct; whether the trained Gaussian representation reproduces the source consistently; and whether mesh extraction damages a representation that otherwise looks acceptable. Diagnose these separately rather than changing all stages together.
3. **Use the same source cameras for comparisons.** Check source image, Gaussian render, polygon render, and untextured surface/depth where available. Confirm coordinate transforms, image orientation, lens model, tile intrinsics, depth conventions and color handling. Reuse saved evidence first. If additional rendering is needed, define a bounded test under the existing memory limits.
4. **Validate depth with independent views and repeated passes.** Adjacent frames and overlapping crops from the same frame are not independent evidence of a reliable room model. Inspect correspondences and physical consistency across genuinely different views. Do not blindly accept or reject a camera model using unscreened matching statistics alone.
5. **Resolve coverage honestly.** Inspect the 29-component candidate and its support audit, and determine which connections are geometrically defensible. Keep separate counts for developed images, candidate camera positions, independently accepted positions, frames actually trained and surfaces reconstructed. Do not force incompatible components together merely to report all frames registered.
6. **Require a visible improvement before broadening the run.** A bounded representative test should reproduce continuous countertop and wall surfaces, sensible rice-cooker/bottle/sink shapes and stable appearance from different views, without the large missing-triangle patterns shown here. Compare directly against original pixels and the rejected baseline.
7. **Only scale a demonstrated remedy.** Define the hypothesis, sample, expected evidence, stopping criteria, time/disk cost and resource guard before a longer run. If the bounded result still fails, report that failure rather than extending it repeatedly or treating a larger texture as progress.

The requested final output remains detailed geometry plus textures for the full room. A Gaussian-only viewer can help diagnose an extraction problem, but it does not by itself satisfy the polygon deliverable. Do not silently replace the requested deliverable or reduce quality requirements.

## 13. Acceptance and communication requirements

Do not claim the task complete until the intended room coverage is present, repeated views align coherently, the kitchen geometry and textures withstand visual comparison, and the actual browser artifact has been exercised in an authorized browser environment or by the user with clearly stated limits.

For future updates:

- Lead with what visibly improved or failed, then state the evidence.
- Say exactly which frames and area a result covers.
- Report uncertainties separately from confirmed failures.
- A successful export, a checkpoint, a correspondence threshold, or a large texture is not visual acceptance.
- Do not blame the user's capture without evidence.
- Do not claim browser testing from syntax checks, HTTP responses or simulated control tests.
- Do not quote stale progress estimates as a promised completion time.
- Do not spend another long run merely to postpone admitting that the method is not working.

The previous assistant's final assessment was: **the result is unacceptable; the workflow failed to deliver the user's intended reconstruction; there is no validated fix yet.** That conclusion should remain visible to the next session.

## 14. What this handoff turn changed

This documentation turn created this Markdown file only. It did not start compute, modify the viewer, change the controller, change the GPU policy, delete artifacts, publish anything, stage files, commit, push, or alter `.gitignore`.

The immediately preceding quality-review turn changed the existing ignored `analysis/native-camera-kitchen-status.json` to `quality_rejected`. Source images, checkpoints, meshes and viewer files were preserved.

Live state and files can change after this report. Use the paths and fingerprints above to establish the starting point, then inspect current evidence before acting.
