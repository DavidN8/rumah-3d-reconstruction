"""Narrative for the single PDF. All technical claims are qualified and sourced."""
from pathlib import Path
import json, math, re

def build_narrative(a,live):
    P,H,T,C,F,page,gap=a.P,a.heading,a.table,a.callout,a.figure,a.page,a.gap
    W,QA,FMT,LITE,REC,WEB,ROOT,TMP=a.W,a.QA,a.FMT,a.LITE,a.REC,a.WEB,a.ROOT,a.TMP
    def R(*paths):return '['+', '.join(a.source(p) for p in paths)+']'
    asset=a.load(WEB/'osmo-asset-report.json')
    build=a.load(WEB/'build-report.json')
    import_manifest=a.load(a.CAP/'capture-manifest.json')
    probe=a.load(FMT/'osv-probe.json')
    fit=a.load(FMT/'kb4-fit-report.json')
    sfm=a.load(FMT/'sfm-independent-audit.json')
    depth=a.load(LITE/'analysis/trusted-depth-scale.json')
    seed=a.load(LITE/'analysis/seed-fisheye.json')
    browser=a.load(WEB/'browser-final-verification.json')
    surface=a.load(WEB/'surface-final-verification.json')['report']
    decision=a.load(QA/'v4-texture-decision-agent.json')
    geom=a.load(QA/'qa-v4-supported-05cm.json')
    oldgeom=a.load(QA/'qa-baseline-trusted-v3.json')
    train=a.load(REC/'training/osmo-surface-v4/config.json')
    v3=a.load(LITE/'training/osmo-lite-trusted-v3/config.json')
    original_report=ROOT/'outputs/Rumah_Osmo_Lite_2026-10-31.png'
    current_report=ROOT/'outputs/Rumah_Osmo_Refined_2026-10-31.png'

    # Cover.
    P('OSMO360<br/>Video-to-mesh processing audit','AuditTitle')
    P('A forensic handoff for the user and Gemini Argon (Architect)<br/>Actual implementation, failure evidence, code and next decisions','AuditDeck')
    C('Current acceptance status: failed',
      'The latest delivered reconstruction remains visually unacceptable to the user. '
      'The user explicitly rejected a larger-file approach and asked for an audit of how the video was processed. '
      'Improved internal scores and a functioning website do not reverse that acceptance failure.','risk')
    F(current_report,'Current published Osmo model, still rejected',
      'This is the actual 30.4 MB release, not a target illustration. It still contains pitted surfaces, gaps, distorted clutter and texture patches. '
      'The image is retained as failure evidence, not evidence of a satisfactory result.',maxh=220)
    P(f'<b>Snapshot:</b> {a.NOW.strftime("%d %B %Y, %H:%M")} Asia/Jakarta (UTC+7). '
      '<b>Scope:</b> the Osmo capture and its complete processing lineage; the website delivery state is recorded separately. '
      '<b>Deliverable:</b> this one PDF, with code printed in the appendices. No ZIP or separate code package is needed to read the report.','AuditSmall')
    P('No video processing, reconstruction training, mesh generation or deployment was performed for this report. '
      'Only existing evidence, code, images and a small read-only website check were used.','AuditSmall')
    page()
    P('Contents and navigation','AuditH1')
    P('Read sections 1-4 first for the decision context. Sections 5-13 trace the actual processing. '
      'Section 14 and the six image plates show why metrics were insufficient. Sections 15-17 contain the issue register, proposed processing experiments and questions. '
      'Appendix A prints complete helper code; Appendix B prints captured argument vectors and the final saved configuration. '
      'The PDF outline and this contents list link to individual sections and code files.','AuditSmall')
    toc=a.TableOfContents();toc.levelStyles=[a.ST['TOC0'],a.ST['TOC1']];a.STORY.append(toc)
    page()

    H('1. What failed, and what this report concludes')
    C('The processing problem comes before the file-size problem',
      'The geometry was not reconstructed from all native-resolution video frames. '
      'The accepted geometry pipeline used 130 sampled pairs of 1920 x 1920 JPEGs, accepted 244 individual lens images, '
      'inferred monocular depth/normal priors, optimized a Gaussian field and then extracted a surface. '
      'The later 3840 x 3840 decode was used for texturing, not a fresh full-resolution geometry reconstruction.')
    P('The user is right that simply making the GLB larger is not a solution. The 17.7 MB model already retained every triangle produced by its selected extractor. '
      'A later 47.4 MB dense candidate also retained all its triangles and still looked poor. '
      'The final 30.4 MB model scored better in several internal checks than that larger candidate, yet the user still judged it unusable. '
      'File size is a downstream packaging constraint; it does not repair unreliable camera geometry, inconsistent depth priors, foreground leakage or a damaged surface. '
      +R(WEB/'osmo-asset-report.json',QA/'dense-photo-asset.json',QA/'qa-v4-texture-pipeline.json'))
    T(['Finding','Evidence status','Implication'],[
      ['Surface holes were created by native visibility cleanup.','Confirmed in inspected source and cull-on/off experiment.','A face can be deleted when only one of its vertices is judged unseen.'],
      ['The native atlas was learned Gaussian DC color, not direct source-photo RGB.','Confirmed in native export/raster code.','Increasing atlas resolution alone could not restore photo detail.'],
      ['The final lineage inherited an earlier affine-depth state.','Confirmed by copied checkpoint and resume records.','No clean trusted-prior reconstruction was completed; residual inherited bias is unresolved.'],
      ['The current source has unmodeled moving/reflected content.','Visible in source/mask images and residual color diagnostics.','A static-scene model can absorb people and mirror reflections as false geometry/color.'],
      ['Better metrics did not establish usable output.','Confirmed by residual images and latest user rejection.','The acceptance gate was insufficient and must change.']
    ],[151,113,a.CW-264])
    P('<b>Accountability:</b> I treated successful rendering, higher coverage and improved internal consistency as sufficient grounds to publish an improvement. '
      'That did not meet the user\'s visual-quality goal. I should have made the upstream processing uncertainties and remaining severe defects the decision point, '
      'rather than presenting incremental metric gains as a completed reconstruction fix.')
    P('<b>What is not established:</b> there is no single experimentally isolated explanation for every rough wall or hole. '
      'This report distinguishes confirmed implementation behavior from likely contributors and untested hypotheses. '
      'It does not claim the camera is defective, that the footage must be recaptured, or that any proposed alternative method will automatically succeed.')

    H('2. Current state and exact delivered artifact',new=True)
    T(['Website choice','Model file','Gzip model transfer','Triangles','Texture'],[
      ['iPhone Fast','21.145 MB','17.853 MB','1,603,164','2 x 2048'],
      ['iPhone Full','435.615 MB','302.564 MB','11,891,853','2 x 8192'],
      ['Osmo (current)','30.351 MB','25.841 MB','2,366,966','1 x 4096']
    ],[110,86,102,111,a.CW-409])
    P('The live release is <b>20261031-osmo-v3</b>. Its Osmo geometry comes from training branch <b>osmo-surface-v4</b>; these version numbers refer to different things. '
      'Both iPhone model hashes were preserved. The source capture and original intermediate runs remain available. '
      'The current Osmo result is a failed visual baseline for further investigation, not an accepted final reconstruction. '
      +R(WEB/'build-report.json',WEB/'deployment-manifest.json',WEB/'public-verification.json'))
    P('<b>Final GLB:</b> models/osmo-lite-30ed8cb766.glb<br/>'
      '<b>Bytes:</b> 30,351,100; gzip 25,840,927<br/>'
      '<b>SHA-256:</b> 30ed8cb76633892b4f4f47e048f1580fce53956a5786cce7771b08d45807989d<br/>'
      '<b>Local export:</b> recovery-v2/exports/osmo-refined-v4.glb','AuditSmall')
    P('The packed model has 2,618,057 UV-split vertices and 70,292,504 decoded geometry bytes (about 67.0 MiB). '
      'One 4096-square RGBA texture with mipmaps is estimated at 89,478,485 GPU bytes (about 85.3 MiB). '
      'Geometry plus texture is therefore already about 152 MiB before framebuffer, decoder, CPU copies and browser overhead. '
      'A 30 MB download is not a 30 MB browser-memory footprint. '+R(WEB/'osmo-asset-report.json'))
    F(ROOT/'outputs/Rumah_Model_Chooser_2026-10-31.png','Current homepage choice gate',
      'The homepage waits for a model selection and Open model. The sizes shown are compressed model transfer estimates, not total page traffic. '
      'This delivery fix is separate from reconstruction quality.',maxh=240)
    P('Read-only recheck during report authoring: '
      f'HTML HTTP {live.get("http_status","not confirmed")}; chooser found: {live.get("contains_chooser")}; '
      f'current bundle reference found: {live.get("contains_final_bundle")}; '
      f'manifest matched the saved release: {live.get("manifest_matches_saved_build")}. '
      'No GLB was downloaded for this recheck. Previously recorded full asset checks remain separately timestamped.','AuditSmall')

    H('3. Actual video-to-model data flow',new=True)
    P('This is the performed pipeline, not a proposed ideal workflow. Several stages used different projections and resolutions. '
      'The transition between those stages is one of the important audit boundaries.')
    a.pipeline()
    P('Key distinction: sparse SfM estimates cameras and feature points; MoGe supplies learned single-image priors; Gaussian training optimizes a field; '
      'meshing extracts an isosurface from that field. This was not a completed conventional dense multi-view-stereo fusion pipeline. '
      'Those representations and objectives cannot be treated as interchangeable guarantees of a correct architectural mesh. '
      +R(LITE/'analysis/sfm.json',LITE/'analysis/geometry.json',REC/'analysis/train-surface-v4.json',REC/'analysis/v4-texture.json'),'AuditSmall')

    H('4. Native media, capture coverage and input interpretation',new=True)
    T(['Property','Recorded value'],[
      ['Master','CAM_20261031005909_0004_D.OSV; 1,162,988,987 bytes'],
      ['Main video streams','Two separate 3840 x 3840 HEVC Main 10 fisheye streams'],
      ['Timing','30000/1001 fps; 1,955 frames per main stream; 65.231833 seconds'],
      ['Pixel/color metadata','yuv420p10le; TV range; BT.709 primaries, transfer and colorspace'],
      ['Proxy retained','Matching LRF; 97,905,073 bytes; optional for processing'],
      ['Capture label','Container encoder says Osmo 360 II'],
      ['Original import SHA','OSV: c88ff8b64ed453e6bb4da61bafaad51bbe1b477c97d7efc66360f053d52aeaa0'],
      ['Proxy import SHA','LRF: ec50a19f6a3b412134a18c75c2b4109c94e11a646893a83d1670da396c5f663c']
    ],[128,a.CW-128])
    P('Those two media hashes were recorded and checked during import from the camera drive. This report does not pretend that the 1.16 GB original was rehashed while writing the PDF. '
      'The final GLB and the code/evidence catalogue were hashed during report creation. '+R(a.CAP/'capture-manifest.json',FMT/'osv-probe.json',FMT/'lrf-probe.json'))
    P('An early interpretation of the LRF as stitched equirectangular video was wrong. It was corrected: the proxy is side-by-side dual fisheye, '
      'and the reconstruction used the two master OSV lens streams, not the proxy and not the embedded MJPEG thumbnail. '
      'No stitched equirectangular reconstruction was completed.')
    P('Main 10 identifies codec bit depth; it does not by itself establish HDR/PQ footage. The recorded transfer is BT.709. '
      'The JPEG extraction reduced this to 8-bit 4:2:0 data. No explicit photometric-calibration or temporal color-normalization pass was performed before geometry training.')
    P('The recording visits the living/dining area and bathroom. It does not reproduce the iPhone capture\'s broader kitchen/bedroom coverage. '
      'This report does not use the Nikon/Samsung results as a controlled benchmark: their source datasets were deleted at the user\'s earlier direction. '
      'The surviving historical reports are context, not evidence that an identical experiment can now be rerun on those captures.')
    page();H('4.1 What the decoded source actually looks like',2)
    F(FMT/'contact-lenses.jpg','Two native fisheye views at representative times',
      'The rear view includes substantial operator/body content. These are native-lens views, not pinhole photos and not a stitched panorama. '
      'A larger nominal camera resolution does not ensure equally dense object detail across the entire 360-degree field.',maxh=300)
    F(FMT/'proxy-timeline.jpg','Proxy timeline',
      'The proxy was useful for rapid scene inspection. Its dual-circle layout was not used as a spherical camera model.',maxh=250)
    C('Capture limitations are not yet a verdict against the footage',
      'The source images show continuous wall/door/ceiling areas where the mesh is torn. That is evidence to investigate processing first. '
      'I have not demonstrated that a new capture is necessary. New footage should be requested only after a missing-angle, blur or parallax failure is measured on the existing recording.')

    H('5. Frame extraction: what was kept and what was discarded',new=True)
    P('The geometry path sampled each master lens at 2 fps and resized it to 1920 x 1920 before SfM, prior generation and training. '
      'Each lens contributed 130 JPEGs, or about 6.65% of its 1,955 encoded frames. Spatial dimensions were halved in each direction, leaving one quarter of the source pixel count. '
      'This is not proof that the selection was too small, but it means the better camera\'s complete temporal/spatial information was not used for geometry. '
      +R(LITE/'analysis/extract.json',LITE/'analysis/frame-extraction.json',LITE/'scripts/prepare_frames.py'))
    a.code_text('[0:v:0]fps=2,scale=1920:1920:flags=lanczos,format=yuvj420p[c0];\n'
      '[0:v:1]fps=2,scale=1920:1920:flags=lanczos,format=yuvj420p[c1]\n'
      '-map [c0] -q:v 2 -fps_mode passthrough images/cam0/frame_%06d.jpg\n'
      '-map [c1] -q:v 2 -fps_mode passthrough images/cam1/frame_%06d.jpg',
      'Executed FFmpeg filter/output pattern (full wrapper in Appendix A)',width=100)
    P('The fps filter uses FFmpeg\'s bin selection/rounding. Frame number n is not evidence that an arbitrary later seek at (n-1)/2 seconds reproduces the same camera exposure. '
      'The later full-resolution decode reused the exact same fps selection and index naming, removing only the resize. '
      'Fourteen samples matched their same-index 1920 images more closely than adjacent indices; resized full-vs-old RGB RMSE was about 1.58-2.65/255. '
      'Full-resolution masks were nearest-neighbor 2x copies, not newly segmented masks. '+R(QA/'qa-full-source-extraction.json',QA/'qa-extract-full.py'))
    T(['Processing decision','What was established','What was not established'],[
      ['Uniform 2 fps sampling','Both lens folders have synchronized names/counts.','No systematic sharpness, motion, overlap or exposure quality ranking selected these frames.'],
      ['1920-square geometry inputs','The exact resize and JPEG settings are recorded.','No clean geometry run compared native 3840 inputs with these reduced images.'],
      ['Full 3840 decode later','Same indexed exposures were verified for photo baking; about 269 MB of JPEGs.','It did not redo SfM, priors or the Gaussian geometry at full native resolution.'],
      ['Nominal timeline labels','Gallery labels use approximately (index-1)/2 seconds.','They are not a per-exposure shutter/rolling-shutter calibration.']
    ],[116,172,a.CW-288])
    P('For a processing restart, frame count should be determined by usable overlap and parallax, not by a desire for a larger model. '
      'A controlled selection experiment would retain sharper frames, add samples only where motion/doorway transitions need overlap, and preserve per-stream timestamps. '
      'Adding many near-duplicate or blurred views can add cost and inconsistency without improving recoverable geometry.')

    H('6. Foreground masks and static-scene assumptions',new=True)
    P('The final accepted masks combined a circular optical border of radius 0.48 times image width with manual foreground outlines. '
      'Camera 1 used ten manually audited anchor polygons and signed-distance interpolation on a 480-square grid; camera 0 used a single hand polygon throughout the sequence. '
      'The foreground was dilated by a 21 x 21 kernel, then subtracted from the usable optical circle. White means usable static scene. '
      +R(LITE/'scripts/foreground_masks.py',LITE/'analysis/foreground-masks.json',LITE/'analysis/frozen-masks.json'))
    P('An earlier optical-flow propagation attempt drifted and was discarded. An attempted SAM2 person-tracking path did not proceed through its required license step; '
      'the final mask record states neural_segmentation_used=false and sam_license_accepted=false. '
      'The source script still contains that historical people branch, so its presence is not evidence that neural person masking was successfully applied.')
    P('The accepted masks were frozen before the final SfM/training lineage. A prematurely started feature extraction was stopped and a fresh SfM workspace was used after mask changes, '
      'avoiding reuse of features computed under the wrong masks. The mask fingerprint is recorded in frozen-masks.json. '
      'That protects reproducibility, but a frozen imperfect mask is still imperfect.')
    F(LITE/'analysis/person-mask-keyframes.jpg','Manual camera-1 mask anchors',
      'Red indicates excluded pixels in this diagnostic overlay. Ten anchors and interpolation are not an exhaustive per-frame segmentation audit. '
      'Outline leakage, camera-relative body changes and unmodeled reflections remain possible.',maxh=350)
    page();H('6.1 A concrete missed dynamic region: the bathroom reflection',2)
    a.panel_grid([
      (TMP/'mirror-fisheye.jpg','A. Raw cam0/frame_000041.jpg; full source resized for this diagnostic.'),
      (TMP/'mirror-mask-overlay.jpg','B. Actual keep-mask overlay. Red is excluded; the reflected person is not fully excluded.'),
      (TMP/'mirror-mask.jpg','C. Actual binary keep mask. A white mirror region remains usable to the pipeline.'),
      (TMP/'mirror-upright.jpg','D. Calibrated upright reference near 20 s, showing the operator in the mirror.')
    ],'Masks did not fully remove reflected moving content',
      'This is direct source evidence for a static-scene violation. It does not prove the cause of every defect. '
      'A reflection can be consistent as image appearance while representing a virtual scene, not the physical wall/mirror substrate.')
    P('The later photographic texture consensus reduced some transient contamination but did not eliminate blue-clothing-like pixels on neutral wall regions. '
      'In the final diagnostic ROI for view 6, the gain variant had 2,059 blue outliers versus 2,012 without gain. '
      'That is a rough color diagnostic, not segmentation ground truth, but it is a documented remaining defect. '+R(QA/'v4-texture-decision-agent.json'),'AuditSmall')
    P('Mask propagation must be audited per stage. SfM, seed construction, training and the custom photo baker explicitly used masks. '
      'Native prior generation saw the original RGB context. The inspected native mesh raster interface receives camera/Gaussian tensors but no source mask bitmap, '
      'although its dataset parser has a mask directory. It is therefore unsafe to assume that occupancy carving honors foreground masks in exactly the same manner as training. '
      'That backend behavior needs a targeted test; this source inspection alone is not proof of a binary bug.','AuditSmall')

    H('7. Calibration, ray conventions and the two-lens rig',new=True)
    P('Factory calibration was decoded from the first OSV djmd metadata sample. The OQ102 layout was interpreted using StreamMeta field 5; '
      'a different layout assumption would point at the wrong data. The recovered lens model had five radial Kannala-Brandt terms, '
      'while the accepted native SfM path used the four-term OPENCV_FISHEYE model. A least-squares radial refit allowed the focal value to change. '
      +R(FMT/'calibration.json',FMT/'decode_calibration.py',FMT/'calib_slots.py',FMT/'fit_kb4.py',FMT/'kb4-fit-report.json'))
    T(['At 1920 x 1920','Lens 0','Lens 1'],[
      ['Initial fx / fy','524.264272 / 524.165153','523.693620 / 523.578869'],
      ['cx / cy','957.357666 / 955.318115','955.848816 / 963.409729'],
      ['k1 / k2','0.045867950 / 0.022022969','0.052244144 / 0.015402567'],
      ['k3 / k4','-0.014674261 / 0.001405352','-0.011822315 / 0.000968885'],
      ['Factory radial domain used','theta up to 98.931 deg','theta up to 98.971 deg'],
      ['Radial fit max / RMS error','0.6055 / 0.1271 pixel','0.5438 / 0.1142 pixel'],
      ['Final SfM fx / fy','525.137990 / 526.849194','522.516383 / 520.852102']
    ],[151,177,a.CW-328])
    P('These are radial-fit errors relative to the recovered factory polynomial, not calibration-target errors or final mesh accuracy. '
      'OPENCV_FISHEYE omits small native tangential terms recorded in the fit report. Their omission was not independently isolated as a cause of the gross defects.')
    a.code_text('X_cam = R_world_to_cam * X_world + t\n'
      'rho = sqrt(x*x + y*y)\n'
      'theta = atan2(rho, z)                 # preserves rays with z < 0\n'
      'theta_d = theta*(1+k1*theta^2+k2*theta^4+k3*theta^6+k4*theta^8)\n'
      'u = fx * theta_d * x/rho + cx\n'
      'v = fy * theta_d * y/rho + cy\n'
      'X_cam = d_ray * unit_ray(u,v)         # ray depth, not camera-axis Z\n'
      'z_depth = d_ray * unit_ray_z          # not interchangeable at fisheye edges',
      'Projection/depth convention used by custom helpers; see source for axis/zero-radius guards',width=100)
    P('The custom reader treats COLMAP binary model ID 5 as OPENCV_FISHEYE with eight parameters. '
      'An older iPhone helper had an incompatible table; it was not used for the accepted Osmo model. '
      'Synthetic helpers checked round trips including rays past 90 degrees, roll and off-origin cameras. '
      'Passing these tests checks implementation math, not whether the selected calibration is physically exact for every exposure. [R1, R3]')
    page();H('7.1 Rig initialization and physical scale',2)
    P('The manifest initialized cam0 as fixed and cam1 approximately back-to-back, with zero translation because a factory baseline was not found. '
      'The cam1 member was not fixed and allowed axial refinement. A CLI rig specification was removed after it conflicted with the manifest rig. '
      'The accepted run used the recorded manifest once. '+R(LITE/'analysis/sfm-manifest.json'))
    P('A fresh read-only calculation for this report found 122 registered same-index lens pairs with an optimized center separation of '
      '<b>0.0186672963 normalized scene units</b> (constant to numerical precision). The final centers therefore did not remain coincident. '
      'This is not a measured physical baseline and cannot independently validate rig calibration, sensor synchronization or metric scale.')
    a.code_text("cameras, images, _ = read_model(dataset / 'sparse/0')\n"
      "centers = {im['name']: -qvec_to_rotmat(im['qvec']).T @ im['tvec']\n"
      "           for im in images.values()}\n"
      "baseline = [np.linalg.norm(center - centers['cam1/' + name[5:]])\n"
      "            for name, center in centers.items()\n"
      "            if name.startswith('cam0/') and 'cam1/' + name[5:] in centers]\n"
      "print(len(baseline), np.quantile(baseline, [0, 0.5, 1]))",
      'Read-only paired-center calculation used in this report',width=100)
    P('The accepted model received one global similarity transform: rotate the source Z-up convention to Y-up using '
      '[[1,0,0],[0,0,1],[0,-1,0]], then multiply scale by 2.6612619112. '
      'The scale came from an assumed median camera height of 1.5 m over a fitted floor. '
      'The projection-ray identity under that transform was verified. No surveyed distance fixed the scale. '
      +R(LITE/'analysis/normalized-frame.json',a.SRC/'normalize_sfm.py'))
    C('Unresolved calibration/timing questions',
      'There is no independent calibration target, measured baseline/control distance, complete per-exposure synchronization audit, '
      'or rolling-shutter/temporal stabilization validation in the evidence. These are uncertainties, not proven causes. '
      'A small sparse reprojection error does not by itself rule out compensated lens/pose error or distorted dense surfaces.')
    P('The geometry path used calibrated native lens images. Training later split them into virtual perspective faces. '
      'Stitching everything into one equirectangular panorama is not automatically safer: a stitched dual-center camera can contain seam/parallax warps. '
      'Any alternative needs an explicit projection/rig model and a controlled comparison rather than an unqualified stitch-first assumption. [R1, R2]')

    H('8. Sparse reconstruction: accepted evidence and limits',new=True)
    P('The native SfM command used ALIKED-n16rot features, LightGlue matching, up to 4,096 features, image-size cap 1,600, '
      'sequential prefilter overlap 12 and 20 neighbor candidates, both lens sequences and the factory-derived fisheye manifest. '
      'Extra distortion parameters were held from refinement while focal/pose optimization proceeded. '
      'The full captured argument vector is printed in Appendix B. '+R(LITE/'analysis/sfm.json'))
    T(['Accepted main component','Result'],[
      ['Registered images / lens groups','244 / 2 (122 images from each lens)'],
      ['Sparse points / observations','125,862 / 412,911 reprojected observations'],
      ['Independent reprojection','Mean 0.9777 px; median 0.8608 px; p95 2.2053 px; max 3.5986 px'],
      ['Invalid fisheye projections in that audit','0'],
      ['Time span','Nominal 0.0-64.5 s'],
      ['Second component','42 images; 30 shared, 12 unique; merge rejected'],
      ['Second-component orientation difference','Median about 1.218 deg; p95 about 1.499 deg after diagnostic alignment'],
      ['Missing from all components','4 sampled images; 16 images are outside the accepted main component']
    ],[185,a.CW-185])
    P('The writer stored point.error as zero, so it would have been wrong to report zero reprojection error. '
      'The independent audit recomputed projection residuals from camera poses, points and recorded observations. '
      'The 0.98-pixel result is useful evidence of sparse self-consistency, not independent ground truth. '
      +R(FMT/'sfm-independent-audit.json',FMT/'audit_sfm.py'))
    F(FMT/'sfm-point-trajectory.png','Accepted sparse structure and trajectory',
      'This is an approximate normalized frame. The 1.5 m camera-height assumption sets the displayed scale; it was not measured.',maxh=220)
    P('Keeping the inconsistent second alignment separate was appropriate. Forcing it into one connected mesh would have hidden a pose discontinuity. '
      'However, no held-out-image pose/geometry validation, measured-distance check or dense per-region confidence map was completed. '
      'Registered images are not the same thing as reliable dense coverage of white walls, reflective regions and occluded floor/clutter.')

    H('9. Learned depth, normals and the seed: a key unresolved lineage',new=True)
    P('MoGe-2 generated depth and normal maps from the registered images using the native geometry command. '
      'The actual log says <b>eight pinhole faces of 485 x 485 per fisheye image</b>, not 768-square output merely because --max-size 768 was supplied. '
      'The source dataset was already reduced to 1920 square. This virtual-face inference and fusion is an upstream geometry-processing stage. '
      +R(LITE/'analysis/geometry.json',LITE/'logs/geometry.log'))
    P('The saved maps represent unit-ray distance in millimetres, not pinhole camera-axis Z. '
      'The custom seed helper used calibrated unit rays including z&lt;0, masked observations, sparse Euclidean range fits, temporal agreement and voxel reduction. '
      'The accepted seed contained 196,461 points under a 200,000-point cap, with approximately 0.0441 scene-unit voxel spacing. '
      'About 44.2% of the evaluated depth candidates passed the recorded temporal consistency test; this is not an independent depth-accuracy figure. '
      +R(LITE/'analysis/seed-fisheye.json',a.SRC/'seed_fisheye.py'))
    P('Initially, each view used an affine fit d_aligned = a*d_raw + b against sparse range. '
      '209 of 244 views were accepted. A later normal audit showed why this could be inconsistent: a uniform positive scale preserves local surface normal direction, '
      'but adding an offset along different viewing rays generally changes surface tangents. '
      'The corresponding normal maps were not transformed to reflect that change.')
    bad=seed['frames']
    rows=[]
    for name in ['cam0/frame_000052.jpg','cam0/frame_000053.jpg']:
        b=bad[name]
        rows.append([name,f'{b["scale"]:.6f}',f'{b["offset"]:.6f}','Rejected in later trusted scale-only set'])
    T(['Example affine fit','Scale a','Offset b','Later treatment'],rows,[173,67,70,a.CW-310])
    P('These examples collapsed depth variation toward a near-constant radial shell. The saved normal audit sampled ten frames and found substantial tangent-normal changes in problematic views. '
      'Raw inferred normals often agreed much better with raw inferred depth tangents, but agreement between two learned outputs is still not physical truth. '
      +R(W/'osmo-normal-audit-20261031/normal-alignment-audit.json'))
    page();H('9.1 What the trusted-depth correction did, and did not do',2)
    P('A fresh scale-only directory was created. Per-view scale was median(sparse_range/raw_ray_depth), with zero offset. '
      'The gate required at least 30 usable sparse observations, actual reprojection at most 4 px, more than 55% inliers within 10% relative range error, '
      'median residual below 10%, p90 below 25%, and sparse range IQR/median at least 0.08. '
      '175 views passed; 69 retained RGB/normal supervision without depth. Original maps, earlier affine maps and poses were left unchanged. '
      +R(LITE/'analysis/trusted-depth-scale.json',a.SRC/'refit_trusted_scale.py'))
    P('Those gates are permissive relative to the centimetre-level wall shape a user expects. At several metres range, a 10-25% relative error can be much larger than a door-frame detail. '
      'They test compatibility with sparse observations, not a full dense surface. Many blank-wall pixels have no sparse constraint.')
    C('The correction was a resume, not a clean rebuild',
      'The rectified branch had already reached step 20,000 using the affine priors. Its full checkpoint was copied into the trusted branch and trained to 40,000. '
      'The final 50,000-step branch was copied from that 40,000 state. The original affine-fitted seed was also inherited. '
      'No completed run in this lineage started from a newly validated scale-only seed and correct priors for its entire optimization. '
      'The amount of residual inherited bias is unmeasured; later weights are not proof that it was removed.','risk')
    P('Other upstream uncertainties remain: no real-data overlap seam maps were produced for the eight MoGe virtual faces before fusion; '
      'no clean ablation compared learned depth, learned normals and purely multi-view geometry; and no full native-resolution geometry experiment was completed. '
      'Projection round-trip tests cannot detect a scene-specific depth mismatch between virtual faces. [R4]')
    P('The approximately 4.4 cm initial voxel spacing, single-image prior uncertainty and masked/dynamic regions can interact. '
      'Gaussian densification can add parameters later, but parameter count is not evidence that a biased initial surface has converged to the right wall.')

    H('10. Training history and effective parameters',new=True)
    a.lineage()
    P('The first pilot trained directly on reduced fisheye data for 20,000 steps with a 1M cap. It was a separate branch and was not the final model\'s parent. '
      'The rectified branch started fresh from the same seed, logged 244 cameras becoming 1,220 virtual images, and progressed to full loaded resolution around step 10,004. '
      'It was stopped after saving step 20,000. The subsequent trusted and surface branches resumed full optimizer state. '
      +R(LITE/'analysis/train-direct-fisheye-v1.json',LITE/'analysis/train-rectified-v2.json',LITE/'logs/train-rectified-v2.log',REC/'analysis/train-surface-v4.json'),'AuditSmall')
    T(['Setting','Trusted v3','Final surface v4'],[
      ['Total target steps','40,000 (resumed at 20,000)','50,000 (resumed at 40,000)'],
      ['Gaussian cap','2,500,000','3,000,000'],
      ['normal_reg_weight','0.04','0.10'],
      ['normal_supervision_weight','0.02','0.06'],
      ['depth_supervision_weight','0.05','0.10'],
      ['max_world_size','Infinity','0.12'],
      ['refine_stop_iter / refine_stop_num_iter','30,000 / 2,500','48,000 / 2,000'],
      ['Effective growth stop','37,500','48,000'],
      ['SH degree / source depth','0 / trusted ray-depth subset','0 / same trusted subset'],
      ['Fisheye warp / train divisor','On / 1','On / 1'],
      ['Masks / scene frame','Frozen; auto-scale false; identity train transform','Unchanged']
    ],[189,147,a.CW-336],padding=4)
    P('The effective refinement stop is max(refine_stop_iter, total_steps - refine_stop_num_iter), not simply the first displayed stop field. '
      'Changing the total target also changed learning-rate progress because max_steps was null. '
      'This was a combined prior/refinement/cap/schedule experiment, not a one-variable proof for any individual setting. '
      +R(QA/'qa-training-config.json',QA/'qa-training-recommendation.txt'),'AuditSmall')
    P('The final trial added exactly 10,000 iterations, took about 306 native seconds, and preserved the original v3 config/checkpoint hashes. '
      'Only 0.111% of v3 Gaussians had an axis above 0.12, carrying 0.274% of summed opacity. The size bound is therefore not a credible sole explanation for broad wall improvement.','AuditSmall')
    P('Evaluation used all cameras with no independent geometry-validation split. SH0 was intentional in this branch; the native mesher reads DC color only. '
      'Merely increasing SH order would not fix a DC-only exported texture. More steps, splats or a cap change also cannot be assumed to solve missing observations or inconsistent priors.','AuditSmall')

    H('11. Surface extraction: where holes and shells appeared',new=True)
    P('Native extraction samples seven points per kept Gaussian, tetrahedralizes the cloud, evaluates camera-dependent occupancy, bisects isosurface crossings, '
      'merges short edges, culls unseen vertices, removes components and repairs some small topology defects. '
      'For the current final source, the selected textured extraction produced 2,577,478 faces before the custom support filter. '
      +R(REC/'analysis/v4-texture.json',REC/'logs/v4-texture.log'))
    T(['Control','Actual final value / meaning'],[
      ['iso / carve-k','0.5 / 3; an occupancy threshold and third-smallest per-camera aggregation, not metric distance'],
      ['merge-factor','1.0; local edge merge with manifold/fold guards'],
      ['max-grid-res','512; acceleration-grid cap, not a target triangle resolution'],
      ['cull-unseen','Disabled for full candidate, then a separate support filter'],
      ['fill-hole-ratio / max-edges','0 / 12; no broad percentage-sized loop filling'],
      ['floater-min-faces','50; component-size filter, not semantic foreground removal'],
      ['degenerate-angle-deg','Explicitly 2 in final extraction; earlier CLI default was 15'],
      ['atlas / chart angle','4096 / 60 degrees']
    ],[158,a.CW-158])
    P('The inspected native cull code removes every face incident to an unseen vertex. Visibility is tested against the mesh itself. '
      'This can turn a partially visible region into a hole rather than merely removing a wholly unsupported backside. '
      'The earlier v3 run logged about 2.34M faces removed in its first cull and about 38k in its second. '
      'Source excerpts and the effective CLI default are printed in Appendix A8.')
    P('Disabling culling retained an isosurface with zero boundary edges and 100% alpha coverage in the six diagnostic views. '
      'It also increased surface area from about 126 to 400.5 approximate square units and below-floor area from 4.91 to 77.24. '
      'It did not reveal a magically correct complete room; it restored large unsupported shells. '
      +R(QA/'qa-baseline-vs-cull-off.json',QA/'qa-cull-off-probe.json',QA/'cull-off-surface-qa.json'))
    a.transparency_chart()
    page();H('11.1 The support filter: useful guard and important bias',2)
    P('The final cull-off geometry was filtered against the refined cull-on v4 probe plus 25,676 good sparse points. '
      'A vertex was supported when near the probe within 0.05 approximate scene units or near accepted sparse support; a face required at least two supported vertices. '
      'Retained attribute bytes and the native UV/image data were preserved. It kept 2,366,966 of the 2,577,478 faces. '
      'No vertices were moved, no height slice was applied, and no synthetic caps were added. '
      +R(QA/'qa-v4-supported-support.json',QA/'qa-support-filter.py',QA/'qa-v4-texture-pipeline.json'))
    C('Why this still cannot recover every real missing wall',
      'The support test is partly circular: it trusts a nearby surface from a probe that already has holes. '
      'A real new surface more than 5 cm from that incomplete reference, with no sparse point nearby, can be rejected. '
      'Blank walls are exactly where sparse support is weak. The filter controls false shells; it is not a dense reconstruction of previously missing surfaces.')
    P('Loosening the older v3 support from 5 to 8 or 12 cm did not improve near-consistent feature-ray counts, but increased backside/underfloor area. '
      'That is why it was not simply loosened until the viewport looked filled. '
      'The fixed v4 support still introduced a small tradeoff relative to its conservative probe: 62 new near rays and 46 lost near rays; '
      '25 newly early-occluded rays and 19 resolved early rays. Net coverage gain did not mean every local surface improved. '
      +R(QA/'qa-dense-comparison.json',QA/'qa-v4probe-supported-paired.json'))
    P('The boundary audit also showed why a larger generic hole-edge threshold was unsafe. Some loops with only 17 or 29 edges were roughly 0.60-0.76 scene units across and strongly non-planar. '
      'Only 173 baseline loops passed a much tighter diameter-at-most-5-cm and plane-max-error-at-most-5-mm candidate test, before view/opening evidence. '
      'None was automatically filled in this delivery. '+R(QA/'boundary-audit.json'))
    P('There is a source/default mismatch worth preserving: Meshing.h documents a 2-degree degenerate-face setting, but mesh_main.cpp initializes 15 degrees. '
      'The final extraction set 2 explicitly. This protects some thin/sliver detail but was not isolated as the dominant hole cause.')

    H('12. Texture reconstruction and why larger textures were insufficient',new=True)
    P('Native meshing reads Gaussian means, scales, opacities and DC color. Its camera color pass re-renders that learned field. '
      'It does not directly project original source RGB into the exported atlas. '
      'The resulting atlas can therefore retain learned blur, mixed foreground colors and imperfect geometry even at a higher resolution. '
      'That behavior is confirmed by the inspected mesh_main.cpp and MeshingRasterHost.cpp excerpts.')
    P('An earlier pilot also exported ordinary PBR material while the iPhone models used unlit photo material. '
      'Changing only that pilot\'s material reduced six-view covered RGB error about 61.5 to 28.0 without changing coverage. '
      '<b>That display issue had already been corrected before the 17.7 MB published baseline.</b> '
      'It is historical evidence, not an explanation that the current model is still accidentally lit twice. '
      +R(FMT/'unlit-v1-edit.json',a.SRC/'qa-v1-unlit-proof.json'))
    P('The new custom baker instead used the full-resolution 3840 photographs with 2x intrinsics and the same distortion/poses. '
      'It rasterized each UV texel into world position/normal, rendered six-face first-hit mesh depth per camera, projected the point through the calibrated fisheye, '
      'checked visibility and eroded masks, then selected a sharp source observation. '
      'A first one-pass version was sharper but did not improve average error and allowed foreground/color seams. '
      'It was not accepted as the final texture. '+R(QA/'photo_bake_agent.py',QA/'baseline-photo-render-check.json'))
    P('The final two-pass version built a clipped-angle-weighted color consensus and variance from visible sources, grouped observations into 3-second time groups, '
      'then admitted a sharp candidate only near that consensus. It required at least three color-consistent groups, RGB distance at most 0.16 and RMS variance at most 0.20. '
      'Unsupported/inconsistent texels retained the native atlas. '
      'Those fallback areas can still contain old learned blur or contamination; a high support percentage does not prove their colors or geometry correct.')
    P('To cover subpixel UV islands, the final GPU raster used the native-like 0.75-pixel conservative edge treatment with clamped barycentrics, prioritizing true interiors. '
      'This fixed an implementation limitation in an earlier exact-texel-center proof. '
      'The synthetic tests checked rolled, anisotropic, distorted, off-origin and greater-than-90-degree cameras, subpixel triangles and first-hit occluder rejection. '
      'They validate code mechanics, not the semantic correctness of masks or the real mesh. '+R(QA/'photo-bake-selftest.json'))
    page();H('12.1 Exposure, holdouts and remaining contamination',2)
    P('A source-track audit found modest per-view exposure variation and smaller white-balance differences. '
      'A bounded scalar correction was fitted in linear RGB, clamped to +/-0.2 stops (roughly 0.87-1.15 gain). '
      'The final fit excluded the six comparison photos entirely; 182 texture-source views had enough usable static-track samples, and the remaining views received no correction. '
      'No per-channel white-balance fit or geometry change was added in that trial. '
      +R(QA/'source-photometric-audit.json',QA/'exposure-gains-texture-sources.json'))
    T(['Same final geometry, 600px renderer','Covered RGB RMSE / 255'],[
      ['Native learned-color atlas','24.760'],
      ['Conservative photographic consensus, no gain','23.332'],
      ['Conservative consensus + bounded scalar gain','22.966']
    ],[a.CW-142,142])
    P('The gain option was selected because it lowered mean six-view error and slightly reduced measured spatial-neighbor view-switch jumps. '
      'This is a small appearance choice, not a solution to poor geometry. '
      'The selected uncompressed photo source was 132,399,252 bytes with a JPEG payload of 11,134,593 bytes before final packing. '
      +R(QA/'v4-final-texture-render-check.json',QA/'v4-texture-decision-agent.json'))
    P('<b>Holdout scope:</b> cam0 frames 3, 25, 41, 61, 81 and 111 were excluded from photo pixel selection and gain fitting. '
      'They were still used for SfM and Gaussian geometry training. These are texture-only holdouts, not independent geometry tests.')
    P('<b>Residual defect:</b> mirror regions, moving-person contamination and patchy white-wall/ceiling colors remain visible. '
      'The final ROI diagnostic did not show universal improvement; view 6\'s blue outlier count rose slightly with gain. '
      'A lower global RMSE can coexist with an unacceptable local artifact.')
    P('The final code is included, including GPU shaders, consensus gates and fallback behavior. It should be reviewed as an experimental photographic baker, '
      'not mistaken for an independently validated production texturing system.')

    H('13. Packing, viewer behavior and deployment',new=True)
    P('The final selected float source was packed using meshopt high, 16-bit positions, 8-bit normals, 12-bit UVs and a 4096 JPEG atlas at quality 86. '
      'It retained all 2,366,966 triangles. No additional geometric simplification was needed. '
      'The maximum bounding-coordinate change reported after packing was about 0.0000362 approximate scene units. '
      'That tiny quantization difference is not reconstruction accuracy. '+R(WEB/'osmo-asset-report.json',WEB/'pack-osmo.mjs'))
    P('The failed 47.4 MB fallback experiment also illustrates why raw size was the wrong target. Its first medium-encoder candidate exceeded 50 MB. '
      'An attempted simplifier rejected loss of an indexed component, rather than silently eroding it. '
      'A high full-geometry compression profile fitted the same faces inside 50 MB without that simplification. '
      'The final v4 model used high compression directly. Neither higher encoder effort nor retained triangle count can make an incorrect source surface correct.')
    P('The viewer defaults to unlit texture. Orbit mode can use back-face culling to see through outside walls/ceiling backs. Walk and fixed source comparisons use both sides. '
      'There is no global horizontal height-clipping plane in the final viewer. '
      'Some Orbit openings are deliberate display behavior, but fixed double-sided renders still show real holes and bad surfaces, so the problem is not merely that viewing mode. '
      +R(WEB/'room-viewer.js',WEB/'surface-final-verification.json'))
    P('The homepage now presents iPhone Fast, iPhone Full and Osmo cards with compressed model-size estimates. '
      'Choosing a card, including following a deep link that preselects one, does not load the model. Open model injects the viewer bundle and launches exactly the selected asset. '
      'Retry and Choose model return to a fresh chooser; they do not silently start another model download. '
      +R(WEB/'choice-core.js',WEB/'chooser.js',WEB/'quota-browser-final.json'))
    T(['Recorded check','What it establishes','What it does not establish'],[
      ['23 loader/choice/packing tests','Expected generation, cancellation, gating, profile and error behavior.','That room geometry is correct or real phones can render it.'],
      ['Private browser download audit','0 completed GLB/image/main-bundle entries before Open; 1 selected GLB afterward, combined with deferred code inspection.','Zero network traffic of every kind; completed entries alone would not rule out an in-flight request.'],
      ['Anonymous public hashes and ranges','The reviewed GLB, manifest and bundle were served, and both iPhone files were preserved.','That publishing is a visual-quality acceptance test.'],
      ['402 x 874 and 884 x 796 frames','The final model rendered and layouts did not overflow in a desktop engine.','Physical Fold 7/iPhone 17 hardware, WebKit/Chrome memory or slow-network compatibility.']
    ],[115,188,a.CW-303])
    P('The service remains the existing Proxmox LXC 710 using nginx and cloudflared, with static assets and an atomic release symlink. '
      'The previous release is retained for rollback. Credentials and private infrastructure access details are intentionally not included. '
      'The read-only HTTP check for this report did not download any model. No hosting changes were made for the PDF.')

    H('14. Visual evidence: same source viewpoints, before and after',new=True)
    P('The next six plates are the main visual acceptance evidence. Each uses the same registered camera view and square crop. '
      'The reference is a calibrated reprojected source photograph. The original is the 17.7 MB model; the v4-native panel isolates the refined geometry with native color; '
      'the final panel uses the selected photographic/gain texture. The matched 600px saved renderer sheets were cropped into readable panels without changing their content.')
    P('Black gaps, pitting, warped edges, patchy neutral walls and incorrect mirror/foreground content should be judged locally. '
      'These are not presentation targets and are not cleaned-up illustrations. The current model remains rejected despite the quantitative changes.')
    T(['Nominal source time','Frame','Main issue to inspect'],[
      ['~1 s','cam0/frame_000003.jpg','Beam/wall junction, door outline and clutter-edge tearing'],
      ['~12 s','cam0/frame_000025.jpg','Door surface/edge integrity and neutral-wall patches'],
      ['~20 s','cam0/frame_000041.jpg','Mirror/person region and hallucinated/incorrect depth'],
      ['~30 s','cam0/frame_000061.jpg','Window/curtain boundary, corner and round-chair geometry'],
      ['~40 s','cam0/frame_000081.jpg','Chair silhouette, corridor surfaces and floor fragments'],
      ['~55 s','cam0/frame_000111.jpg','Long white wall, skirting/floor edge and table/chair detail']
    ],[90,166,a.CW-256])
    P('The six source images were withheld only from texture/gain construction, not from the geometry/pose stages. '
      'For exact final source identifiers and per-view measurements, see the evidence catalogue and v4-final-texture-render-check.json. '
      +R(QA/'baseline-consensus-render-check.json',QA/'v4-final-texture-render-check.json'))
    scenes=['Living wall and beam','Closed door and wall junction','Bathroom mirror and operator','Window, curtain and round chair','Chair and corridor','Long wall, floor edge and table']
    times=[1,12,20,30,40,55]
    for i,(scene,seconds) in enumerate(zip(scenes,times),1):
        page();H(f'14.{i} {scene} - nominal {seconds} s',2)
        a.panel_grid([
          (TMP/f'view{i}-source.jpg','A. Calibrated source photograph.'),
          (TMP/f'view{i}-original.jpg','B. Original 17.7 MB native-texture model.'),
          (TMP/f'view{i}-native-v4.jpg','C. Refined supported v4 geometry, native learned-color texture.'),
          (TMP/f'view{i}-final.jpg','D. Current 30.4 MB result: same v4 geometry, photographic consensus and scalar gains.')
        ],scene,
          '600 x 600 rendered/reference panels; same pose. Better local color or coverage is not proof of correct missing geometry. '
          'The residual defects are part of the evidence, and the user has not accepted the final panel.')

    H('15. What the numerical checks mean - and where they failed',new=True)
    T(['Same 4,711 tracked rays','Original v3','V3 dense fallback','Final supported v4'],[
      ['Near-consistent first hit','61.240%','62.152%','64.657%'],
      ['Early occlusion','19.465%','19.783%','18.934%'],
      ['Behind observed point','17.279%','17.555%','16.175%'],
      ['Missing intersection','2.017%','0.509%','0.234%'],
      ['Approx. surface area','125.98','182.78','161.19'],
      ['Area below fitted floor - 0.10','4.913','7.146','3.251'],
      ['Underfloor area fraction','3.900%','3.910%','2.017%']
    ],[184,99,111,a.CW-394])
    P('The ray sample comes from stable, masked main-component SfM observations, with good points checked against reprojection. '
      'A hit is near when within max(0.05 scene units, 2.5% of observed range). Early/behind classify the first mesh hit relative to that tolerance. '
      'These same sparse points helped reconstruct the scene, so this is in-sample consistency, not independent geometry truth. '
      +R(QA/'qa-baseline-trusted-v3.json',QA/'qa-v4-supported-05cm.json',QA/'qa-baseline-v4-supported-paired.json'))
    C('The remaining error is large even after the improvement',
      'Only 64.66% of these already favorable feature rays are near-consistent. About 18.93% intersect a surface too early and 16.18% too late. '
      'The final p90 absolute first-hit error is approximately 0.202 scene units, roughly 20 cm only under the assumed scale. '
      'Reducing the small missing-ray category is not equivalent to repairing the other incorrect surfaces.','risk')
    P('The paired transition audit matters: the final supported mesh gained 307 near rays but lost 146 near rays relative to the original. '
      'It introduced 95 early occlusions while resolving 120. Net improvement hides local regressions. '
      'Likewise, the six render views do not span every surface, and errors on covered pixels ignore missing pixels by construction.')
    T(['Renderer and scope','Original','Final'],[
      ['Browser 400px: covered fraction','97.253%','98.680%'],
      ['Browser 400px: transparent fraction','2.747%','1.320%'],
      ['Browser 400px: covered RGB RMSE /255','26.692','23.025'],
      ['Independent saved renderer 600px: covered RGB RMSE /255','26.729','22.966']
    ],[a.CW-170,85,85])
    P('The 400px and 600px numbers are separate measurements; they are not interchangeable. Each model\'s RGB score uses its own covered pixels, '
      'so changing geometry also changes the evaluated pixel set. A low-frequency blur can reduce RMSE even when it looks worse; '
      'a wrong opaque shell can eliminate transparency. Neither should certify a good room mesh. '
      +R(WEB/'surface-final-verification.json',QA/'v4-final-texture-render-check.json'))
    page();H('15.1 Wall shape, topology and acceptance gaps',2)
    T(['Fixed common-grid region','Centered p90 displacement','Neighbor-step p90 difference'],[
      ['Wall family candidate 4','7.81 -> 5.17 cm','3.65 -> 2.69 cm'],
      ['Nearby hypothesis 7 (same wall family)','6.75 -> 4.86 cm','3.28 -> 2.43 cm'],
      ['Floor candidate 0','6.20 -> 5.10 cm','2.73 -> 2.01 cm'],
      ['High ceiling candidate 12','3.59 -> 3.53 cm','1.85 -> 1.72 cm'],
      ['Wall candidate 8','14.81 -> 15.02 cm','7.85 -> 8.11 cm']
    ],[210,146,a.CW-356])
    P('These use identical approximate 5 cm cells, the same fitted planes and common valid hits. Median offsets were removed to separate shift from waviness. '
      'Candidates 4 and 7 are not independent demonstrations on different rooms. Other walls remain mixed and the ceiling\'s centered spread changed little. '
      'Even the improved wall family still has visible centimetre-scale unevenness. '+R(QA/'plane-audit-v4-common-grid.json',QA/'plane-audit-recommendation.txt'))
    P('Topology also needs careful interpretation. The packed final asset has 234,556 indexed components because the atlas splits vertices at UV/chart boundaries. '
      'That is not a count of physical floaters or holes. Position-welded topology and surface area must be checked separately. '
      'Conversely, a single large connected component can still be badly pitted, folded or geometrically wrong.')
    P('The plane audit found background feature rays passing through many proposed wall-fill cells. On one strong wall hypothesis, '
      '194 of 926 missing cells had at least two such negative witnesses. They may be real openings, finite wall boundaries or visible background. '
      'A large rectangular cap would hide that evidence. Absence of a negative witness is also not positive proof of a wall. '
      'No blanket plane completion was performed.')
    C('Acceptance process correction',
      'The user\'s latest rejection is the current acceptance outcome. Download success, SHA checks, a larger triangle count, lower RMSE and a good-looking aggregate chart are technical observations, '
      'not substitutes for the requested usable reconstruction. Future promotion needs agreed visual/structural tests, including the worst regions, before another public replacement.','risk')

    H('16. Issue register and causal confidence',new=True)
    T(['Issue','What is known','What remains uncertain'],[
      ['Reduced/ungated geometry frames','2 fps, 1920-square JPEGs; no quality-based frame selection audit.','How much usable full-resolution/temporal evidence was discarded in the problematic regions.'],
      ['Dynamic and reflected content','Manual masks miss some operator/reflection content; final blue outliers remain.','Exact contribution of each unmasked interval to geometry corruption.'],
      ['Monocular prior fusion','Eight 485-square faces per image; affine-depth phase preceded correction.','Per-face depth seams, accumulated prior bias and dense physical correctness.'],
      ['Warm-started correction','Final lineage inherited affine-fitted seed and 20k optimizer state.','Whether a clean trusted-prior restart would materially repair the scene.'],
      ['Surface representation/extraction','3D Gaussian field; camera occupancy; harsh per-vertex visibility deletion.','Whether the field or the extractor dominates each remaining local hole.'],
      ['Support-filter circularity','Distance to a holed probe rejects far additions; controls shells.','How many real but unsupported wall patches were suppressed.'],
      ['Photographic texture limits','Actual-photo bake improves aggregate color; fallback, seams and contamination persist.','How to separate true exposure differences, geometry misprojection and semantic foreground.'],
      ['Sparse/metric validation','Good internal reprojection; no surveyed scale or external dense reference.','Actual dimensional accuracy, calibration drift and rolling-shutter effects.'],
      ['Quality gate failure','Publication checks passed; user still rejects the result.','The exact acceptable structural/visual threshold has not been jointly established.']
    ],[107,198,a.CW-305])
    P('<b>Already corrected, not current explanations:</b> proxy/equirectangular misinterpretation; the incompatible older model-ID reader; duplicate rig specification; '
      'drifting optical-flow masks; the pilot\'s PBR double lighting; and the use of affine offsets for the final supervision maps. '
      'Correcting those issues did not establish that all damage from their earlier states had disappeared.')
    P('<b>Not demonstrated:</b> defective Osmo hardware; inadequate original capture resolution; an anti-aliasing/codec fault; a specific stabilization or rolling-shutter mechanism; '
      'a need to recapture immediately; or that a bigger cap, more steps, stitch-first export or one alternative algorithm will solve the scene.')

    H('17. Recommended processing direction and questions for the Architect',new=True)
    C('Recommended first experiment: clean input/geometry restart on a small hard region',
      'Freeze the current rejected result and its evidence. Select the beam/white-wall/door area plus the bathroom mirror segment. '
      'Audit the original exposures, masks, calibration and depth-face seams there before another whole-scene training run. '
      'Keep delivery compression and the website constant so processing changes can be assessed independently.')
    T(['Experiment','Change only what is needed','Required decision evidence'],[
      ['1. Decode/selection audit','Use exact native timestamps and full RGB; rank blur/motion/overlap; retain additional frames only where justified.','Contact sheets and measured quality/overlap versus the actual 2 fps set. No geometry-size claim.'],
      ['2. Projection/rig audit','Check real-image edge alignment and synthetic planes through every backend; preserve lens identity and rig timing.','Error by image radius, both lenses and time; measured scale/baseline if available.'],
      ['3. Static-scene masks','Per-frame person/hand masks and explicit mirror policy; verify boundary cases and reflected movement.','Mask overlays for every selected hard interval; no stale feature/depth caches.'],
      ['4. Prior audit','Measure overlap disagreement between MoGe faces and views; compare RGB-only / normals / trusted-depth subsets.','Depth-cycle, tangent-normal and feature-range errors, with per-region confidence and rejected maps.'],
      ['5. Clean restart','New seed and all state from the accepted inputs; do not inherit the affine-depth checkpoint.','Same fixed references plus genuinely held-out pose/geometry views; inspect worst surfaces, not only means.'],
      ['6. Representation pilot','If needed, compare dense MVS/fusion or a surface-oriented method on the same calibrated virtual views.','Controlled geometry quality at a fixed delivery budget; reject if confidence is only visual opacity.'],
      ['7. Texture after geometry','Reproject original RGB with validated visibility, masks and conservative color correction.','Seams, temporal outliers and structural edges on fixed source views; label unsupported regions.'],
      ['8. Delivery last','Pack the accepted surface under the user\'s 50 MB allowance and keep the explicit chooser.','No source-face loss from packaging; actual physical phone load/memory test when available.']
    ],[108,204,a.CW-312])
    P('These experiments were not executed while writing this report. A classical depth-fusion path is conditional on genuinely consistent calibrated depths; '
      'fusing the same biased monocular maps can simply make a wrong surface smoother. A 2DGS/surface-oriented pilot is a methodological option, not a promise and not the method already used. [R2, R4, R5]')
    page();H('17.1 Questions requiring an architectural decision',2)
    questions=[
      'Should the primary deliverable be an observed photogrammetric surface, or an explicitly regularized architectural model with inferred wall planes? Those have different truth/acceptance requirements.',
      'Do we first prove the native dual-fisheye rig across all backends, or use calibrated perspective virtual faces with complete provenance? How do we avoid counting virtual faces as independent observations?',
      'Should the camera\'s native stabilization/rolling-shutter behavior and two-stream timing be independently calibrated before dense optimization?',
      'Is the first priority a clean run with corrected priors and seed, rather than another resume of the current Gaussian field?',
      'What is the geometry policy for mirrors and reflective doors/windows: exclude reflection evidence from geometry and model a substrate, or preserve only observed ambiguous scan content?',
      'What measured evidence should permit a local wall/ceiling fill, and how will door/window/background rays veto it?',
      'Which dense method should be tested on the small region first, and what held-out geometry/edge-straightness criteria would reject it?',
      'How should the 69 views without trusted depth be handled, and how much weight should monocular normals receive without independent validation?',
      'What counts as an acceptable result for the user: wall/door continuity, local waviness, mirror handling, object silhouette and residual clutter? Which reference viewpoints must pass?',
      'Only after processing is validated: what missing view or motion-blur evidence would justify asking for new footage, and what precise capture change would address it?'
    ]
    for i,q in enumerate(questions,1):P(f'<b>{i}.</b> {q}')
    C('Decision boundary',
      'The report does not authorize or execute a new reconstruction, a broad synthetic fill, a new public replacement, or a request for more capture. '
      'It provides the failed baseline, source code and evidence for choosing the next processing experiment. The working chooser can remain while visual reconstruction quality is unresolved.')

    H('18. Code and evidence reading guide',new=True)
    P('The appendices include the actual helper implementations used for extraction, masking, calibration, seeding, prior alignment, resume/refinement, '
      'surface support, photographic baking, packing, diagnostics, viewer loading and deployment. '
      'They expose the processing choices and constraints instead of presenting a simplified idealized pseudocode pipeline.')
    T(['Appendix group','Why it matters'],[
      ['A1: media and calibration','Exact fps/resize/JPEG filter, manual mask anchors, OQ102 extraction and KB refit.'],
      ['A2: geometry and seeding','Strict binary reader, greater-than-90-degree rays, affine fitting, temporal gates, normalization and trusted scale-only replacement.'],
      ['A3: refinement/support','Full checkpoint copy, all effective v4 changes, extraction commands and the spatial support predicate.'],
      ['A4: photo construction','Actual OpenGL projection/visibility/consensus/gain shaders and source-camera export.'],
      ['A5: delivery and diagnostics','Full-geometry packing profiles, fallback rules, ray consistency, topology and reference rendering.'],
      ['A6/A7: website and publication','Explicit consent gate, bounded loader, actual viewer and atomic static release process.'],
      ['A8/B/C','Native behavior excerpts, actual captured command arrays/final config, and evidence fingerprints.']
    ],[160,a.CW-160])
    P('Important dependency boundary: the report does not contain the entire Spirula engine or pretrained model weights. '
      'The used native binary is reported as the retained 2026.10.16 runtime; geometry inference logged the MoGe-2 ViT-L normal ONNX model and RTX 5080. '
      'Processing helpers used the retained host-model environment; the photographic baker used the separate bundled Python environment with workspace-local OpenGL dependencies. '
      'The code itself shows the exact paths and imports. A reproducible rebuild still needs those dependencies and the original media.')
    P('The full source snapshot is not automatically identical to an earlier historical wrapper state. For example, run_stage.py now names the rectified precursor, '
      'whereas the direct-fisheye pilot used different arguments preserved in its stage record. Appendix B therefore prints the actual argument vectors and final stored configuration. '
      'No script was run to regenerate the model for this document.')
    P('The packet is intentionally one PDF: the core evidence and code are readable here, with bookmarks and line numbers. '
      'Local evidence paths and SHA-256 values support later inspection, but no separate ZIP is required for this review.')
