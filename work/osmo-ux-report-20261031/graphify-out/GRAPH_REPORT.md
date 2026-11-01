# Graph Report - C:\Users\bombe\Documents\Codex\2026-10-27\files-pasted-by-the-user-system\work\osmo-ux-report-20261031\code  (2026-10-31)

## Corpus Check
- Corpus is ~10,731 words - fits in a single context window. You may not need a graph.

## Summary
- 212 nodes · 385 edges · 25 communities (18 shown, 7 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 31 edges (avg confidence: 0.68)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Renderer state|Renderer state]]
- [[_COMMUNITY_Pinhole mask construction|Pinhole mask construction]]
- [[_COMMUNITY_Public asset build|Public asset build]]
- [[_COMMUNITY_Fresh camera preparation|Fresh camera preparation]]
- [[_COMMUNITY_Delivery and LoD policy|Delivery and LoD policy]]
- [[_COMMUNITY_Load lifecycle|Load lifecycle]]
- [[_COMMUNITY_Camera framing|Camera framing]]
- [[_COMMUNITY_Mask reprojection|Mask reprojection]]
- [[_COMMUNITY_Explicit chooser|Explicit chooser]]
- [[_COMMUNITY_Navigation modes|Navigation modes]]
- [[_COMMUNITY_Full rebuild controller|Full rebuild controller]]
- [[_COMMUNITY_Heldout evaluation|Heldout evaluation]]
- [[_COMMUNITY_Cross-view depth validation|Cross-view depth validation]]
- [[_COMMUNITY_Mirror annotation|Mirror annotation]]
- [[_COMMUNITY_Job provenance|Job provenance]]
- [[_COMMUNITY_Frame selection|Frame selection]]
- [[_COMMUNITY_Scale-only depth fitting|Scale-only depth fitting]]
- [[_COMMUNITY_Source contact sheets|Source contact sheets]]
- [[_COMMUNITY_SOG compression|SOG compression]]

## God Nodes (most connected - your core abstractions)
1. `loadAsset()` - 23 edges
2. `main()` - 16 edges
3. `$()` - 14 edges
4. `invalidate()` - 14 edges
5. `setMode()` - 13 edges
6. `home()` - 11 edges
7. `orbitCamera()` - 10 edges
8. `resize()` - 10 edges
9. `release()` - 9 edges
10. `preset()` - 9 edges

## Surprising Connections (you probably didn't know these)
- `main()` --calls--> `camera_from_manifest()`  [INFERRED]
  masking/repair_pinhole.py → geometry/operator_pinhole.py
- `main()` --calls--> `pinhole_map()`  [INFERRED]
  masking/repair_pinhole.py → geometry/operator_pinhole.py
- `fast_unwarp()` --calls--> `unwarp_mask()`  [INFERRED]
  masking/repair_pinhole.py → geometry/operator_pinhole.py
- `main()` --calls--> `save()`  [INFERRED]
  geometry/operator_pinhole.py → geometry/normalize_fresh_sfm.py
- `main()` --calls--> `digest()`  [INFERRED]
  geometry/operator_pinhole.py → geometry/normalize_fresh_sfm.py

## Import Cycles
- None detected.

## Communities (25 total, 7 thin omitted)

### Community 0 - "Renderer state"
Cohesion: 0.06
Nodes (27): camera, canvas, deviceSignals, euler, forward, frames, framingPoints, keys (+19 more)

### Community 1 - "Pinhole mask construction"
Cohesion: 0.17
Nodes (20): process(), Materialize calibrated pinhole RGB/mask views with independently checked poses., selected(), digest(), finalize(), infer(), main(), optical_keep() (+12 more)

### Community 2 - "Public asset build"
Cohesion: 0.09
Nodes (18): asset, assetPath, {build}, bundle, bundleName, carried, chooser, here (+10 more)

### Community 3 - "Fresh camera preparation"
Cohesion: 0.19
Nodes (19): coverage(), digest(), fresh_path(), main(), model_paths(), Gate fresh SfM, apply one +Y-up similarity, and build a train-only sparse seed., Report direct geometric links between camera paths revisiting the same room., Reproject actual XYZ independently; ignore native point.error placeholder. (+11 more)

### Community 4 - "Delivery and LoD policy"
Cohesion: 0.18
Nodes (11): OSMO_LIMITS, chooseQuality(), pinchRatio(), readModel(), selectModel(), withDeadline(), NATIVE_LIMITS, nativePolicy() (+3 more)

### Community 5 - "Load lifecycle"
Cohesion: 0.29
Nodes (14): $(), applyCameraData(), chooseAnotherModel(), controlsEnabled(), disposeModel(), inspectModel(), loadAsset(), loadMetadata() (+6 more)

### Community 6 - "Camera framing"
Cohesion: 0.26
Nodes (14): calibratedProjection(), clearRecorded(), componentVisibility(), fittedOrbitRadius(), focus(), invalidate(), orbitCamera(), pan() (+6 more)

### Community 7 - "Mask reprojection"
Cohesion: 0.27
Nodes (10): camera_from_manifest(), main(), output_guard(), pinhole_map(), Calibrated CPU native-fisheye <-> virtual-pinhole masks for SAM diagnostics.  Th, Columns map CV virtual rays to native CV rays; phi=0 right,90 bottom., unwarp_mask(), virtual_basis() (+2 more)

### Community 8 - "Explicit chooser"
Cohesion: 0.23
Nodes (9): $(), canonicalChoice(), createChoiceGate(), createLoadLifecycle(), choices, fail(), gate, initial (+1 more)

### Community 9 - "Navigation modes"
Cohesion: 0.54
Nodes (8): angles(), home(), orient(), preset(), release(), setMode(), updateMode(), updateSurface()

### Community 10 - "Full rebuild controller"
Cohesion: 0.40
Nodes (3): Continue the verified explicit-pinhole workflow; stop before visual release QA., run(), save()

### Community 12 - "Cross-view depth validation"
Cohesion: 0.67
Nodes (3): process(), Validate scale-only pinhole depths across distinct training timestamps.  Only pi, sample_image()

## Knowledge Gaps
- **47 isolated node(s):** `here`, `work`, `pub`, `old`, `require` (+42 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **7 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `nativePolicy()` connect `Delivery and LoD policy` to `Renderer state`, `Public asset build`, `Load lifecycle`?**
  _High betweenness centrality (0.048) - this node is a cross-community bridge._
- **Why does `canonicalChoice()` connect `Explicit chooser` to `Renderer state`?**
  _High betweenness centrality (0.022) - this node is a cross-community bridge._
- **Why does `main()` connect `Fresh camera preparation` to `Pinhole mask construction`?**
  _High betweenness centrality (0.013) - this node is a cross-community bridge._
- **Are the 10 inferred relationships involving `Path` (e.g. with `process()` and `selected()`) actually correct?**
  _`Path` has 10 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Materialize calibrated pinhole RGB/mask views with independently checked poses.`, `Continue the verified explicit-pinhole workflow; stop before visual release QA.`, `Fit positive, zero-offset depth scales against qualified training SfM anchors.` to the rest of the system?**
  _66 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Renderer state` be split into smaller, more focused modules?**
  _Cohesion score 0.06050420168067227 - nodes in this community are weakly interconnected._
- **Should `Public asset build` be split into smaller, more focused modules?**
  _Cohesion score 0.09090909090909091 - nodes in this community are weakly interconnected._