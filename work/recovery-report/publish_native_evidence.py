from pathlib import Path
import json,shutil,html,hashlib
IP=Path(r'C:/Users/bombe/OneDrive/Documents/ChatGPT/Ruang Kamare/roomscan-reconstruction/data/20261027_IPHONE_WIDE');RUN=IP/'recovery-v2';review=IP/'review';src=RUN/'analysis/verification-full-native';out=review/'verification-native'
out.mkdir(exist_ok=True);(IP/'analysis/fixed-renders').mkdir(exist_ok=True)
for p in src.glob('*'):
    if p.suffix in ['.png','.json']:shutil.copy2(p,out/p.name)
for i in range(1,9):shutil.copy2(src/f'after-{i:02d}.png',IP/f'analysis/fixed-renders/{i:02d}-compare.png')
shutil.copy2(src/'after-overview.png',IP/'analysis/fixed-isometric.png');shutil.copy2(RUN/'analysis/allviews-elevation-and-floorplan.png',IP/'analysis/fixed-elevation-and-floorplan.png');shutil.copy2(src/'fixed-controls-check.json',IP/'analysis/fixed-controls-check.json');shutil.copy2(src/'fixed-standalone.png',IP/'analysis/fixed-standalone.png')
m=json.loads((RUN/'analysis/architect-review.json').read_text(encoding='utf-8'));report=json.loads((RUN/'analysis/full-native-verification.json').read_text(encoding='utf-8'))
cards=''
for i,v in enumerate(m['views'],1):
    cards+=f'<section><h2>{i:02d}. {html.escape(v["label"])} - frame {v["frame"]}</h2><p>{html.escape(v["finding"])}</p><div class="pair"><figure><a href="verification-native/before-{i:02d}.png"><img loading="lazy" src="verification-native/before-{i:02d}.png"></a><figcaption>Before - previous export</figcaption></figure><figure><a href="verification-native/after-{i:02d}.png"><img loading="lazy" src="verification-native/after-{i:02d}.png"></a><figcaption>After - full native delivery</figcaption></figure></div></section>'
doc='<!doctype html><html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Full native reconstruction - verification</title><style>body{font:16px system-ui;max-width:1240px;margin:auto;padding:26px;background:#111922;color:#e9f0f5}a{color:#79d2e8}h1{font-size:30px}h2{font-size:21px}p{line-height:1.5}.summary{padding:20px;background:#20323e;border-radius:10px}.pair{display:grid;grid-template-columns:1fr 1fr;gap:16px}figure{margin:0}img{width:100%;height:auto}figcaption{padding:7px;color:#b6c9d6}section{margin-top:34px}@media(max-width:750px){.pair{grid-template-columns:1fr}}</style><h1>Full native reconstruction</h1><div class="summary"><p><b>11,891,853 triangles - 435.6 MB.</b> The complete native extraction is the primary model. Delivery size and triangle caps are removed; no post-extraction simplification is applied.</p><p>All 33 browser/offline checks passed on the RTX 5080, at about 240 FPS in walk and orbit. The 584.6 MB offline viewer embeds the exact native model.</p><p><a href="index.html?mode=orbit&amp;rev=full-native">Open full room</a> · <a href="iPhone-Full-Room-preview.html" download>Download offline viewer</a> · <a href="models/iphone-full-room.glb" download>Download native GLB</a> · <a href="verification-native/Gemini-Argon-Recovery.pdf">Architect report</a></p><p>Visible defects remain around the kitchen doorway, cabinet edges and some small objects. The report records these alongside the improvements. Scale and kitchen registration remain approximate.</p></div><section><h2>Dollhouse overview</h2><a href="verification-native/after-overview.png"><img src="verification-native/after-overview.png"></a></section>'+cards+'<section><h2>Verification records</h2><p><a href="verification-native/fixed-controls-check.json">33 browser and offline checks</a> · <a href="verification-native/depth-and-hole-checks.json">Depth layers and native-preservation checks</a></p></section></html>'
(review/'checks.html').write_text(doc,encoding='utf-8')
readme=f'''IPHONE WIDE - FULL NATIVE PRIMARY DELIVERY
Updated 27 October 2026 after the user's explicit choice: full native, bigger size acceptable, remove delivery limitations.

OPEN
  Local viewer: http://127.0.0.1:53251/?mode=orbit&rev=full-native
  Launch: open_viewer.bat
  Offline: iPhone-Full-Room-preview.html (584,632,983 bytes; no server or internet required)
  Source comparisons and report: checks.html

PRIMARY GEOMETRY
  exports/iphone-full-room.glb and review/models/iphone-full-room.glb
  11,891,853 triangles; 435,614,584 bytes; two 8192 x 8192 JPEG90 textures.
  SHA-256 {report['mesh']['sha256']}
  No post-extraction simplification, count/byte cap, ownership crop or geometry floor/roof deletion.
  Roof cutaway is a viewing plane; full geometry remains available.
  The offline file streams 18 embedded pieces. Decoded model bytes match the native GLB exactly.

COMPONENT FRAME
  Kitchen: one original component; living/corridor/bedroom: one original component.
  No temporal bedroom split and no independent bedroom tilt.
  All 501 original camera poses and 75,213 sparse points exported to a consistent two-calibration COLMAP derivative.
  Active colmap-gpu/merged/sparse/0/FRAME.json is version 3.
  Fresh training datasets and the older checkpoint coordinate frames are preserved.
  Legacy temporal commands reject accidental reuse; seed one calibrated component at a time.

VERIFIED
  Actual Chrome / RTX 5080: all 33 control, source-preset and offline checks pass.
  Walk and orbit both measured approximately 240 FPS at 1440 x 1000 in this session.
  Native arrays retained exactly; nine identical-camera depth tests add zero newly empty pixels.
  Actual large standalone opens from disk with zero HTTP requests.

REMAINING RECONSTRUCTION DEFECTS
  Torn switch-side kitchen-doorway wall; cabinet-edge perforations; kitchen-front floor gap; soft/warped small objects.
  Approximate kitchen join retained: wider matching did not provide three orthogonal distributed constraints.
  Native preservation is not surveyed accuracy or proof of a fully complete reconstruction.

PROVENANCE AND WORKFLOW
  Primary baseline: recovery-v2/exports/apartment-allviews-raw.glb
  Recovery stages: scripts/20_component_recovery.py, 21_recovery_pilot.py, 26_all_usable_coverage.py, 22_recovery_export.py.
  Native promotion and integrity: scripts/25_verify_promote_recovery.py, 29_publish_full_native.py, 30_verify_native_delivery.py.
  Exact commands, source audits and full-native checks: recovery-v2/analysis and recovery-v2/logs.
  The small 2M / 81.7 MB mesh and 0.65/640 kitchen experiment are archived review variants, not primary delivery.
  The previous working primary is preserved in recovery-v2/review/before-rebuild and backups/before-component-rebuild-20261027.
  Nikon and Samsung model assets were not changed or recomputed.
'''
(review/'README.txt').write_text(readme,encoding='utf-8');(RUN/'README.txt').write_text(readme,encoding='utf-8')
print('Published full-native gallery, records and README.')
