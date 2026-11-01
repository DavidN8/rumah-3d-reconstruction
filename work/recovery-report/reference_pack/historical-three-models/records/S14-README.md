# Bedroom + bathroom models · 2026-10-19

[Download RuangKamar-models.zip from Google Drive](https://drive.google.com/file/d/1uNabZmV9T8D9bVE_avVtBBNcTS0o--Yk/view?usp=drivesdk).
Anyone with the link can download them. The source repository remains private.
No source video or training environment is needed to use this viewer.

## Automatic setup

From the repository root, with Python 3.10+:

```sh
python scripts/video-scan/preview.py --download
```

The command downloads **one file: `RuangKamar-models.zip` (about 1.22 GB)**, checks
its SHA-256 hash, extracts and verifies all three models, and opens the viewer.
The ZIP is cached under `.roomscan-viewer/`. The download helper, gdown 5.2.0, is installed
in a project-local environment; it does not change the system Python packages.
The browser viewer itself uses vendored JavaScript and can run offline afterward.

Keep the terminal running. Ctrl+C stops the server. It listens only on 127.0.0.1
and chooses a free port starting at 53247; use the URL it prints. Use
`--prepare-only` to download and verify without starting the server, or
`--no-browser` to start it without opening a browser tab. `--port 54000` changes
the starting port. On macOS/Linux, use `python3` when necessary.

Allow 3 GB free disk space for the three models and the cached ZIP. Use
a desktop browser with hardware acceleration; 8K textures and millions of
triangles can be demanding on low-memory devices. A slow first load does not
mean the model has failed.

## Files

There is one ZIP in the Drive folder. It contains the cleaned full model, the
roofless dollhouse, and the unchanged original for comparison. All three appear
in the model selector after setup. Reports stay in the GitHub repository.

The download link, exact byte count, and SHA-256 values are in
[`manifest.json`](manifest.json). Each GLB embeds its textures and can also be
opened directly in Blender or another glTF-compatible editor.

| Model inside the ZIP | GLB size | Geometry |
| --- | ---: | --- |
| Cleaned dollhouse | 419.8 MB | 8,569,710 triangles, roof removed |
| Cleaned full model | 425.8 MB | 9,080,740 triangles, ceiling retained |
| Original combined model | 543.1 MB | 9,400,291 triangles, unchanged original |

Do not open the HTML with `file://`; the local server supplies the required file
loading and byte-range support. Drive holds the download; the interactive viewer
runs on your computer.

## Manual download fallback

Download `RuangKamar-models.zip` from the Drive link above, then run:

```sh
python scripts/video-scan/preview.py --archive "PATH/RuangKamar-models.zip"
```

Use the actual downloaded file path, with quotes for spaces. The script verifies
the archive and its models before opening the viewer. Keep the ZIP and model
binaries out of Git.

## What changed

- Removed 165,546 triangles belonging to small detached components. Connectivity
  is analysed using welded positions, while retained positions, normals, and UV
  seams are preserved in the output.
- Removed 142,127 doorway debris triangles and 15,012 triangles outside the
  inspected bathroom envelope. This crop is specific to this capture.
- Added 3,134 triangles for an inferred doorway surround, jambs, lintel, and
  threshold. The centre passage stays open. This geometry is a separate node
  named `INFERRED_REPAIR_Doorway_surround_threshold`, so an editor can adjust or
  remove it without touching the scanned surfaces.
- Cut the roofless version at a common height with exact triangle-plane
  intersections and interpolated UVs/normals. This makes the cut level without
  globally smoothing furniture or decimating the room meshes. Wall regions below
  that plane can still have ragged reconstruction edges.
- Preserved both original 8192 × 8192 PNG texture images **byte for byte**. The
  doorway repair uses an additional projected photograph texture. There was no
  global texture resize, rebake, decimation, or remesh.
- Removed obsolete buffer data from the exported GLBs, reducing file size without
  reducing the retained surface detail.

See [`cleanup-report.json`](cleanup-report.json) for counts and texture hashes,
[`doorway-repair-config.json`](doorway-repair-config.json) for the repair/crop
coordinates, and [`clean_room_mesh.py`](../scripts/video-scan/clean_room_mesh.py)
for the implementation. The repair configuration is tied to this scan, not a
universal room-cleanup preset. Recreating the photo projection requires its
source frame, which is embedded as the repair texture in the cleaned GLB.

## Limits and editing

The bedroom and bathroom were reconstructed separately and approximately aligned
at the doorway. They remain separate editable room meshes, not a single welded,
watertight surface. The repaired surround bridges some missing coverage; it does
not recover unseen details. Bathroom mirrors, occlusions, and some wall/floor
gaps are still incomplete. The wall cut does not manufacture a solid wall cap.
Scale is uncalibrated, so do not use the model for accurate dimensions.

The scan comes from a 132.91-second recording containing 7,964 frames at about
59.92 fps. The reconstruction sampled stable views rather than treating every
adjacent video frame as independent evidence. The moving-door/light transition
was excluded from training. This helps consistency but does not create detail
that was never visible to the camera.

The room meshes are distinct from Gaussian splat exports. These downloads are
textured polygons suitable for browser viewing and geometry editing. The original
video, frame collection, training checkpoints, and splat files are not part of
this lightweight developer handoff.

## Developer entry points

The [release verification record](verification.md) describes the download,
geometry-preservation, and browser checks performed for this package.

- [`../CLAUDE.md`](../CLAUDE.md): automatic preparation instructions for Claude
  and other coding agents.
- [`../scripts/video-scan/viewer/`](../scripts/video-scan/viewer/): viewer HTML,
  navigation, and dependency licenses. Edit here and rerun `preview.py` to refresh
  the generated local site.
- [`../scripts/video-scan/package_models.py`](../scripts/video-scan/package_models.py):
  single-ZIP packaging layout. Replace the current Drive package, then record its
  Drive ID and URL in the generated manifest. Keep exactly one file in the Drive
  release folder; publish documentation and reports only in GitHub.
- `models.json` and `cameras.json`: model catalog and selected recorded camera
  poses. These are reconstruction coordinates, not geographic coordinates.

The viewer uses [model-viewer](https://modelviewer.dev/docs/index.html) 4.4.0
(Apache-2.0) and meshoptimizer 0.25.0 (MIT), both vendored with licenses. Automatic
Drive downloading uses [gdown](https://github.com/wkentaro/gdown). The models do
not require an external viewer service or account login after download.
