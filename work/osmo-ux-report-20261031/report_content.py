from pathlib import Path
import json,math

def narrative(d):
    A=d.A;P=d.P;H=d.H;T=d.table;F=d.fig;C=d.cite;B=d.box
    P('Osmo360 reconstruction<br/>and viewer review','title')
    P('Why the latest result is blurry, lacks a dollhouse view, and feels worse to control than iPhone Fast / Lite.','deck')
    P('<b>Prepared for Gemini Argon (Architect)</b><br/>31 October 2026 | Asia/Bangkok (UTC+7)<br/>Audited release: 20261031-osmo-clean-v1<br/>Website: <link href="https://rumah.shizuku.rest/">https://rumah.shizuku.rest/</link>','small')
    B('Current product verdict: rejected by the user','The delivered Osmo experience has not met the requested standard. Successful loading, retaining nearly three million Gaussians, and removing an earlier bathroom obstruction did not establish acceptable sharpness, dollhouse viewing or control quality.',True)
    F(str(d.HERE/'assets/user-latest-osmo.png'),'The latest user-reported result','The user supplied this 1891 x 1240 screenshot with the complaint about blur, missing dollhouse view and frustrating controls. The original image is embedded without AI enhancement. It has no visible diagnostics, so its exact camera pose, device, LoD state and viewport scale are unknown. '+C('user'),maxh=280)
    P('This is one self-contained PDF. It includes the quality comparisons, performed processing steps, key numerical results, relevant code, an issue ledger, proposed corrective work, and questions for architectural review. No reconstruction or live-site change was made while preparing this report.','small')
    d.page();H('Contents and reading map')
    P('Read the findings and product comparison first. The pipeline and diagnosis sections explain what the evidence establishes. Proposed work is explicitly separated from work already performed. Code, per-view scores and provenance are included in the appendices.','small')
    toc=d.TableOfContents();toc.levelStyles=[d.S['toc']];d.STORY.append(toc)

    H('1. Executive finding and responsibility',new=True)
    P('The user is right to reject the current experience. The latest Osmo model is visibly soft, and the viewer does not offer the whole-apartment dollhouse interaction available in iPhone Fast, the current name for the preferred Lite option. These are separate failures and require separate remedies.')
    P('I changed the Osmo delivery from a textured triangle mesh to a native Gaussian radiance-field view to bypass damaging mesh extraction and support filtering. That helped preserve visible room coverage and removed an opaque obstruction at a difficult bathroom camera. I then made the Gaussian branch start inside the room, disabled mesh-specific cutaway controls, and treated preservation of an interior viewpoint as a navigation success. The resulting product lost an interaction the user expected. '+C('viewer','review'))
    T(['Requirement','Current evidence','Verdict'],[
        ['Overall sharpness','The supplied screenshot is blurry. Source-matched images also show detail loss before web compression.','Not accepted'],
        ['Dollhouse / whole-room overview','Top view and See inside are hidden for Gaussians; native auto-fitting is bypassed.','Missing feature'],
        ['Controls comparable to Lite','Same labels lead to different starting modes, orbit targets and framing behavior.','Product regression'],
        ['Continuous interior coverage','Seven saved poses are more coherent and the bathroom obstruction is gone; extreme views remain rough.','Partial improvement'],
        ['Download and startup','45.18 MB file; public desktop Chrome reached a visible room in 12.45 s in one test.','Technical check passed'],
        ['Fold 7 / iPhone 17','Desktop viewport checks exist; no physical-device confirmation.','Unverified'],
    ],[110,300,d.CW-410])
    H('Where my acceptance process failed',2)
    P('I placed too much weight on loading successfully, keeping the source splat count, numerical transport fidelity and fixing one severe bathroom failure. I did not require a usable dollhouse overview, mode/control parity, a full-viewport sharpness review, or reproduction of the user\'s freely navigated complaint view. My release record says those narrower checks passed; it is not evidence that the user experience was satisfactory. '+C('release_gate','browser','public'))
    B('The immediate direction','Restore the intended viewing experience and diagnose the blur with controlled comparisons. Increasing file size, point count or training time without isolating the cause is not a justified next step.')

    H('2. What is actually being compared',new=True)
    P('The website has three choices but only two capture families: iPhone Fast and iPhone Full are derivatives of the same iPhone reconstruction; Osmo is a different recording and a different representation. iPhone is the correct product-experience baseline. These captures do not form a controlled camera-hardware benchmark. Their camera positions, room coverage, exposure, reconstruction recipes and rendering representations differ. '+C('manifest','iphone_fast','iphone_native'))
    m=A['manifest']['models']
    T(['Property','iPhone Fast / Lite','iPhone Full','Current Osmo'],[
        ['Representation','Textured GLB mesh','Textured GLB mesh','SOG Gaussian radiance field'],
        ['File size',f'{m["phone"]["fileBytes"]/1e6:.2f} MB',f'{m["native"]["fileBytes"]/1e6:.2f} MB',f'{m["osmo"]["fileBytes"]/1e6:.2f} MB'],
        ['Expected wire size',f'{m["phone"]["downloadBytes"]/1e6:.2f} MB with gzip',f'{m["native"]["downloadBytes"]/1e6:.2f} MB with gzip','45.18 MB; already compressed'],
        ['Geometry / primitives','1,603,164 triangles','11,891,853 triangles','2,997,908 source Gaussians'],
        ['Colour representation','Two 2048 x 2048 atlases','Two 8192 x 8192 atlases','Per-Gaussian colour, SH degree 2'],
        ['Initial interaction','Auto-fitted Orbit; see-through exterior','Interior Walk by default','Interior Walk by default'],
        ['Overview tools','Top, See inside, fit-to-model Orbit','Top, See inside, fit-to-model Orbit','Top / See inside hidden; local Orbit'],
        ['Main coverage','Kitchen, living / corridor / bedroom','Same source reconstruction','Living / dining and bathroom capture'],
    ],[107,132,132,d.CW-371])
    P('A triangle count and a Gaussian count are not interchangeable quality measures. Keeping every source Gaussian in the download does not imply photographic detail, a watertight surface, or that every primitive is drawn on screen. The public Gaussian branch selects an LoD representation within a rendering budget. '+C('policy'))
    H('The iPhone Lite reference is useful but not perfect',2)
    F('iphone_dollhouse','The preferred iPhone Fast interaction','Retained 29 October 2026 browser capture. The visible UI identifies the 21.1 MB / 1.60M-triangle phone model, with Orbit, Top view and See inside. This model still has holes and imperfect geometry. Its advantage here is usable overview and familiar interaction. The current model bytes have the same verified identity; the capture is historical, not a new physical-phone test. '+C('iphone_dollhouse','iphone_height','iphone_fast'),maxh=405)

    H('3. Visual evidence: blur exists before compression',new=True)
    P('At the exact saved camera, the source photograph resolves stickers, packaging edges and appliance details more clearly than the reconstructed Gaussian. The original PLY render and the compressed SOG render look very similar to each other. This places substantial appearance loss upstream of web-file packing. It does not isolate which training or preprocessing choice caused that loss. '+C('matched','packing'))
    F('fridge_detail','Matched fridge-detail comparison','Diagnostic crops use the same 600 x 600 reference grid and exact saved source camera. The 1200-pixel source crop was resized to that grid before the same rectangle was extracted. Crops are not sharpened or AI repaired. Left: source photograph. Centre: final original PLY, all-source drawing. Right: the SOG file, also all-source drawing.',maxh=245)
    F('floor_fan_detail','Matched fan, floor and small-object detail','The blur and rough object boundaries remain visible in the original Gaussian, not just the compressed transport. These are same-camera appearance diagnostics; the source capture also participates in SfM pose estimation.',maxh=245)
    P('The latest user screenshot is a larger, freely navigated view, not one of the seven documented 600-pixel captures. Its camera and renderer state were not supplied. The controlled figures explain part of the complaint, but cannot quantify the exact error in that screenshot or attribute it to its device. '+C('user','matched'))

    H('4. What the quality numbers prove - and do not prove',new=True)
    ev=A['nativeEval'];matched=A['matched']
    T(['Measurement','Observed result','Interpretation'],[
        ['All 188 held-out virtual views',f'Mean PSNR {ev["meanPsnrDb"]:.2f} dB; median {ev["medianPsnrDb"]:.2f} dB; minimum {ev["minimumPsnrDb"]:.2f} dB.','There is real appearance error and a wide quality range. This is not a sharpness guarantee.'],
        ['All valid pixels, pooled',f'PSNR {ev["weightedPsnrDb"]:.2f} dB; RMSE {ev["weightedRmse255"]:.2f} on a 0-255 scale.','Weighted by the number of valid pixels, unlike averaging per-view dB values.'],
        ['GT/source identity check',f'Unique 188-to-188 image mapping; maximum full-resolution RMSE {ev["maximumGtSourceRmse255"]:.3f}/255.','Avoids assuming eval file numbering is chronological or corresponds to a guessed camera.'],
        ['Original vs SOG at seven poses',f'Minimum {matched["packingMinimumPsnrDb"]:.2f} dB; mean RGB RMSE {matched["packingMeanRmse255"]:.2f}/255.','Small packing loss in the tested renderer configuration. It does not certify all public LoD or free-view states.'],
        ['Public desktop startup','12.45 s to a visible room in one Chrome / RTX 5080 session.','Delivery evidence only; not image-quality acceptance or a mobile benchmark.'],
    ],[125,180,d.CW-305])
    P('The native trainer\'s unmasked whole-face average was about 11.74 dB. Many virtual faces contain black lens padding or excluded operator regions, while the renderer can predict the background there. The later audit applies the exact binary keep-mask and measures all 188 held-out views consistently. The masks are not chosen from pixel error. This explains why the valid-pixel result differs; neither score substitutes for the user\'s visual judgement. '+C('native_eval'))
    H('Seven documented source cameras',2)
    rows=[]
    for row in matched['poses']:
        rows.append([f'{row["timestampSeconds"]:.2f}s',row['split'],f'{row["nativeVsSource"]["psnrDb"]:.2f}',f'{row["packedVsSource"]["psnrDb"]:.2f}',f'{row["packingVsNative"]["psnrDb"]:.2f}'])
    T(['Time','Appearance split','Original vs source dB','SOG vs source dB','SOG vs original dB'],rows,[66,100,113,113,d.CW-392])
    P('Two of these times are held out from Gaussian appearance training. SfM uses the same capture to estimate their cameras, so these are not independent survey or geometric-ground-truth tests. A mostly plain wall can score reasonably well while providing little evidence about fine object detail. '+C('matched'))
    B('An important renderer mismatch','The seven compression comparisons used a 600-square canvas, LoD disabled, extSplats enabled, linear depth sorting and SH2. The public viewer uses LoD, extSplats disabled, radial sorting and a different viewport. Therefore the 40 dB packing figure does not bound the public viewer\'s total visual error. '+C('viewer','matched'))

    H('5. Why the dollhouse view is missing',new=True)
    P('This is a confirmed viewer implementation gap. It is not established that the Osmo footage or Gaussian splatting inherently prevents a dollhouse presentation. The current application simply does not implement an equivalent Gaussian cutaway and whole-scene fitting path.')
    T(['Exact code behavior','User-visible consequence'],[
        ['controlsEnabled(): hides shade, see-inside and top whenever nativeGaussian is true.','The Top view and See inside functions disappear for Osmo.'],
        ['updateSurface(): the Gaussian branch forces seeInside=false and returns.','The mesh back-face-culling toggle has no Gaussian counterpart.'],
        ['setMode(): native Orbit targets camera position + forward x 2.','Orbit pivots around a nearby interior point instead of the apartment centre.'],
        ['fittedOrbitRadius(): immediately returns the existing radius for Gaussians.','The mesh fit-to-model framing algorithm is deliberately bypassed.'],
        ['loadAsset(): auto-Orbit is enabled only when the asset is not Gaussian.','iPhone Fast opens as an overview; Osmo opens inside the room.'],
    ],[245,d.CW-245])
    P('Source locations: room-viewer.js lines 43-49, 71-101, 268 and 386. The code comments explicitly describe preserving the interior viewpoint. That was my implementation decision. It should not have been treated as satisfying the user\'s whole-apartment viewing requirement. '+C('viewer'))
    H('Why mesh culling is not a drop-in Gaussian cutaway',2)
    P('For the iPhone mesh, See inside uses front-face rendering to hide exterior back faces. It does not apply a blanket horizontal height cut, so tall cabinets and door/window proportions are retained. Gaussian ellipsoids are alpha-composited primitives, and the mesh material-side switch is not an equivalent control. Osmo needs a deliberate, reversible visibility/cutaway design. '+C('viewer','iphone_height'))
    P('Spark documents per-splat RGBA edits using signed-distance shapes, including planes and boxes. This gives a plausible renderer-side route to test a cutaway. It is not implemented here. The current SplatMesh is created with editable:false, and a correct design must verify edit scope, LoD interaction and structural preservation with the pinned SDK. A single global height plane risks repeating the cabinet-cutting problem. (R1) '+C('viewer'))

    H('6. Why the controls feel inconsistent',new=True)
    T(['Action','iPhone Fast / Lite','Osmo'],[
        ['Open model','Orbit fitted to sampled mesh geometry, FOV 42 degrees.','Walk from the first interior camera, FOV 75 degrees.'],
        ['Select Orbit','Centred on model bounds; oblique fitted overview.','Keeps the current interior position and uses a local target two units ahead.'],
        ['Drag in initial mode','Orbits around the apartment.','Changes yaw/pitch while staying inside.'],
        ['Wheel / pinch in Walk','Moves the camera through the scene.','Same Walk semantics; it is not an overview zoom.'],
        ['Top / See inside','Available.','Hidden / disabled.'],
        ['Reset or R','Returns to interior Walk home; it does not preserve the initial Lite overview.','Also returns to interior Walk home.'],
        ['Recorded view then drag','Leaves calibrated framing for free-view FOV.','Also changes from square calibrated framing to free-view FOV 75.'],
    ],[112,195,d.CW-307])
    P('Both branches share many event handlers, but their defaults and camera targets change the meaning of the same gestures. A functional movement button is not evidence of a good interaction model. The saved 350 ms button test checked delivery, motion and release in a desktop narrow viewport; it did not assess real phone gestures, comfort or discoverability. '+C('viewer','browser'))
    H('Additional control weaknesses',2)
    P('The camera can freely cross walls because this viewer has no collision model. Recorded views are unlocked on the first input: clearRecorded() removes reference framing and changes the FOV, which can cause an apparent zoom/framing jump. Reset is not mode-aware. These are code-confirmed behaviors or shared limitations, not measured proof of the exact action that frustrated the user. '+C('viewer'))
    H('Scene framing metadata also needs correction',2)
    P('The Osmo bounds were exported as the minimum and maximum of all finite sparse SfM points. Their vertical span is about 33.03 normalized scene units, while the saved interior review-camera heights include about 0.46 to 1.54. This is a poor starting point for a future whole-room fit and needs robust occupied-scene bounds. Current native auto-fit is bypassed, however, and walking speed is a fixed numeric value. The oversized bounds are not proven to be the cause of current walking speed. '+C('camera_export','cameras','viewer'))

    H('7. Pipeline comparison: iPhone and Osmo',new=True)
    P('The iPhone options are not independent reconstructions. Fast / Lite is a delivery derivative of the full iPhone model. Its lower file size comes from geometry simplification, texture resizing and packing. The user\'s preferred dollhouse behavior comes from the mesh viewer branch. '+C('iphone_fast','iphone_native'))
    H('iPhone reconstruction and Lite delivery',2)
    d.flow('iPhone',[
        ('Perspective source video',['1080 x 1920 portrait source; about 156.9 seconds.','Retained source record: 4705 decoded frames.']),
        ('Calibrated reconstruction components',['501 original camera poses; two original SfM components.','Kitchen and shared living / corridor / bedroom frame.']),
        ('Recovery geometry and training',['Fresh depth/normal inputs and corrected dense seeds.','40k kitchen pilot; 50k living component, then all-usable-view correction.']),
        ('Native mesh extraction and assembly',['Selected 0.5 merge / default grid 512 extraction recipe.','One consistent similarity per original component; shared living/bedroom.']),
        ('Full native delivery',['11,891,853 triangles, 435.6 MB, two 8K textures.','No post-extraction simplification in the selected full delivery.']),
        ('Fast / Lite derivative',['1,603,164 triangles; two 2K textures; 21.1 MB GLB.','Geometry quantization: position 16, normal 8, UV 12 bits.']),
        ('Mesh viewer',['Whole-model Orbit fitting, Top, back-face See inside.','A familiar architectural overview, with remaining source/model defects.']),
    ])
    P('The iPhone recovery also has limitations: approximate rather than surveyed scale, uncertain inter-component alignment evidence, and local mesh defects. Its comparison photos were not all held out from its final all-usable-view training. Therefore its reports cannot be used as a fair held-out PSNR ranking against Osmo. '+C('iphone_native','iphone_coverage','iphone_report'))
    H('Current Osmo pipeline',new=True)
    d.flow('Osmo',[
        ('Original dual-fisheye OSV',['Two 3840 x 3840 HEVC 10-bit streams, 1955 frames per lens.','65.2318 seconds at 30000/1001 fps; original OSV retained.']),
        ('Adaptive selection and masks',['226 synchronized pairs / 452 native JPEG images.','Per-frame operator masks and whole-mirror exclusions.']),
        ('Fresh native-resolution SfM',['Native fisheye features / matching; one connected component.','452 registered images; one +Y-up normalization.']),
        ('Materialized calibrated pinhole views',['2219 virtual 1200-square views; 90-degree pinhole fields.','2031 train / 188 eval; splits grouped across lens and timestamp.']),
        ('Validated learned geometry and seed',['768-square inferred depth/normals; positive scale, zero offset.','439 cross-view-qualified maps; 1,381,699-point dense seed.']),
        ('Cold-start Gaussian optimization',['50k steps, 3M cap, Mip primitive, SH2.','Conservative position/noise updates and strong floater suppression.']),
        ('SOG and interior viewer',['491.66 MB PLY -> 45.18 MB SOG, source count retained.','Public LoD budgets 2M desktop / 750k phone; no dollhouse path.']),
    ])
    P('This branch directly delivers Gaussians; it does not run the old mesh carving/support filter. Bypassing that stage avoided one class of destructive mesh holes, but did not deliver the architectural surface and cutaway experience the user expected. '+C('trainJob' if 'trainJob' in A['sources'] else 'full_train_job','viewer'))

    H('8. Video, selection and resolution: exact current state',new=True)
    T(['Stage','Actual resolution or count','Limit / interpretation'],[
        ['Original recording','2 x 3840 x 3840, HEVC 10-bit, 65.2318 s.','Source is preserved. LRF preview media is not the reconstruction input.'],
        ['Working source JPEGs','452 images at 3840 x 3840.','8-bit JPEG decode; not lossless 10-bit appearance training.'],
        ['Selection','652 candidate pairs, 226 selected pairs.','Adaptive sharpness and optical image motion; not measured translation or guaranteed parallax.'],
        ['Temporal density','Average about 3.46 selected pairs/s; largest gap 0.7007 s.','Not uniform sampling; 226 distinct times, not 2219 independent viewpoints.'],
        ['Gaussian RGB training','1200 x 1200 virtual views, focal length 600 pixels.','Native-resolution SfM does not mean native-resolution Gaussian RGB supervision.'],
        ['Learned maps','Actual stored depth/normal images: 768 x 768.','Geometry guidance resolution; RGB training remains 1200 square.'],
        ['Matched visual QA','600 x 600 all-source renders.','Useful controlled evidence, but insufficient alone for a large-viewport sharpness judgement.'],
    ],[128,178,d.CW-306])
    P('The selection compares joint lens sharpness and image motion and retains synchronized pairs. About 11.6% of source times were used. A high candidate count, more virtual faces or more pixels processed does not create new physical baseline. Doorway overlap, stable calibration and actual translation remain important. '+C('selection','pinhole'))
    H('A more honest way to describe the resampling',2)
    ang=A['angularSampling'][0]
    P(f'The current front pinhole spans 90 degrees across 1200 pixels. With the recorded native fisheye calibration, the same horizontal angular interval spans about {ang["nativeHorizontalPixelSpanAcross90Degrees"]:.0f} native image pixels, and the local centre sampling ratio is about {ang["nativeCenterSamplesPerVirtualCenterPixel"]:.2f} native pixels per virtual pixel. The ratio varies over the fisheye projection. It is incorrect to compare 3840 and 1200 as if they covered the same rectangular field of view, but there is still meaningful resampling of appearance information. '+C('pinhole'))
    P('This is a confirmed input-resolution choice, and a plausible contributor to loss of small detail. It is not a proven single cause of all the blur. The original PLY is also affected by learned geometry, optimization, primitive size, per-view appearance modelling and coverage. No resolution-only ablation was completed.')

    H('9. Masks, calibration and sparse reconstruction',new=True)
    P('The rebuild used true per-selected-frame neural segmentation of operator regions, additional hand/body prompts and reviewed manual corrections. Whole mirror-glass polygons exclude reflected people and virtual geometry. Source binary masks use 255 for keep and 0 for exclude. The native-mask builder applies an operator margin of 32 pixels and a mirror margin of 16 pixels. Reprojection into virtual views uses nearest-neighbour sampling. '+C('masks','pinhole'))
    P('Mask readiness covers 452 native images. Earlier review work included 44 manual pinhole repairs, rejected static-scene false detections and mirror annotations across both bathroom visits. This did not establish perfect hair or body-boundary exclusion. The lower-scoring native eval views still show rough fringe regions; some source views have only a small amount of valid background. A blanket larger mask can remove legitimate background support and is not automatically an improvement.')
    F('mirror_masks','Retained mirror-mask review evidence','This is a dated processing diagnostic, not a final-model quality certificate. Mirror and operator exclusions protect pose/geometry estimation, but do not reconstruct unseen reflected content or guarantee every boundary is clean.',maxh=250)
    H('Calibration and registration findings',2)
    P('The current runtime is the isolated Spirula 2026.10.30 build. Factory KB5 calibration was approximated by the native KB4 fisheye model with recorded native-pixel residuals around 1.21 / 1.09 maximum and 0.254 / 0.228 RMS over the audited domain. The optimized relative lens translation is nonzero, about 0.02097 normalized scene units. It is not a surveyed physical lens separation. The initial zero translation was an initialization, not proof that the final rig had zero baseline.')
    P('Fresh ALIKED / LightGlue matching used the masks at native 3840-square resolution. A 3-pixel PnP threshold fragmented registration. Increasing the native-pixel threshold to 6, with strong inlier requirements and cached features/matches, produced one component containing all 452 images and 226 synchronized pairs. The selected model has 552,160 sparse points. Independently recomputed mean source reprojection error is about 1.405 pixels, with 95th percentile 3.625 pixels. '+C('sfm'))
    P('A single +Y-up similarity was then applied to points and cameras. The transform scale is about 2.98175, and it establishes a consistent normalized frame, not measured metres. Explicit pinhole reprojection later checked about 1.59 million observations with mean error about 0.967 virtual pixels. These checks establish camera/coordinate consistency; they do not certify photographic sharpness or all reconstructed surfaces. '+C('sfm','pinhole'))

    H('10. Depth validation, dense seeding and optimization',new=True)
    H('How relative learned depth was accepted',2)
    P('MoGe-2 inference ran on the explicit pinhole images. Per training view, a positive scale s maps relative Euclidean ray range into the normalized SfM frame: depth_scene = s x depth_raw. The additive offset is exactly zero. Qualified SfM anchors require observations across at least three distinct training timestamps, stored error at most 1.5 native pixels and actual virtual reprojection at most 2.5 pixels. Scale fitting requires at least 40 observations, 70% within a 5% residual band, median residual at most 3%, 90th percentile at most 10%, and support in at least five cells of a 4 x 4 image grid. '+C('scale'))
    P('440 views passed the scale gate. A target pixel then survives only if it agrees within 5% with depth from at least two other distinct training timestamps. Evaluation images, depths and colours do not participate in this guidance/seed stage. The outcome was 439 trusted maps and 119,266,081 trusted pixels. Normal guidance was restricted to these validated pixels. '+C('trusted'))
    P('The depth PNG convention is uint16 / 1000 = normalized scene units. The factor 0.001 is an encoding scale, not a claim that this Osmo reconstruction was measured in metres. Combining sparse train-only seeds with validated dense candidates produced 1,381,699 seed points after voxel reduction. The recorded seed voxel size is 0.0219893 scene units; it is an initialization choice, not the final model\'s guaranteed spatial resolution. '+C('trusted'))
    H('The exact current training choices',2)
    cfg=A['config']
    keys=[('Iterations / refinement stop','50000 / 35000'),('Splat cap','3,000,000'),('Initialization','Fresh dense seed; no resume checkpoint and no old init PLY'),('RGB views','2031 explicit 1200-square train views'),('Primitive / appearance','Mip / spherical harmonics degree 2'),('Depth guidance','Weight 0.05; trusted ray depth; encoded-unit factor 0.001'),('Normal guidance','Weight 0.01; only trusted pixels'),('Surface regularizers','Normal 0.04; depth distortion 0.01; normal distortion 0.01'),('Floater / size policy','strong suppression; maximum world size 0.12'),('Position learning','means LR 0.000064 -> 0.0000008'),('Noise schedule','16 -> 0.16'),('Frame / resolution','No additional runtime pinhole warp; no progressive resolution; no automatic pose scaling')]
    T(['Setting','Executed value'],keys,[160,d.CW-160])
    P('Training completed 50,000 steps in 30 minutes 46.928 seconds, producing 2,997,908 exported Gaussians. The conservative recipe was chosen to avoid floaters and an opaque shell. Its effect on fine-detail recovery has not been isolated. Strong surface regularization, conservative position updates, seed density and Mip filtering are plausible trade-offs to test, not established individual root causes. Mip filtering also controls aliasing; simply disabling it may make the result noisier. (R4) '+C('full_config','full_train_job'))

    H('11. Export, compression and the actual display path',new=True)
    P('The final 491,657,919-byte floating-point PLY was packed to a 45,177,102-byte SOG file using @playcanvas/splat-transform 3.10.3. A temporary header-only Mip declaration was added for packing; the source PLY was not modified. Export checks verify the Gaussian count, SH degree and antialiased model tag. SOG is a quantized transport, not byte-for-byte preservation of every float attribute. '+C('packing'))
    T(['Layer','Private fidelity review','Public website'],[
        ['Input','Original PLY and SOG separately','SOG only'],
        ['Source count','2,997,908 in both','2,997,908 in file'],
        ['LoD','Disabled; all-source draw','Enabled; 2M desktop / 750k phone target'],
        ['Extended splat storage','extSplats:true','extSplats:false'],
        ['Sorting','Linear depth','Radial'],
        ['Blur options','preBlurAmount 0; blurAmount 0.3','Same nominal blur values'],
        ['Image size','600 x 600; pixel ratio 1','Responsive canvas; DPR capped 1 phone / 1.25 desktop'],
        ['Starting view','Calibrated reference camera','Interior Walk home; free-view FOV 75'],
    ],[124,183,d.CW-307])
    P('The phone draw budget is about 25% of the file\'s primitive count and the desktop budget about 67%, but LoD selection is not a uniform permanent deletion of that percentage. It can choose coarser representations. The whole SOG is still downloaded and an LoD tree is prepared in the browser. Therefore this policy does not by itself bound transient decode/build memory. '+C('policy','browser'))
    P('Spark documents a memory/precision trade-off between packed and extended splat storage, and offers prebuilt LoD trees and paged RAD streaming. These are relevant prototype options, not completed improvements. Their total bytes, retained appearance and real-device peak memory must be measured. The current phone budget was manually chosen and is more restrictive than some SDK platform defaults; no physical-device quality test justified it. (R2)')

    H('12. What the rebuild improved, and what it did not',new=True)
    P('The earlier fresh normals-only full run reached 50k steps but produced an opaque obstruction at the original 51.9519-second bathroom camera. The same issue was independently visible in its native evaluation output, so it was not only a browser problem. A controlled removal of 319 visibility candidates did not materially improve it and was rejected. Those results were not published as the final clean reconstruction.')
    F('before_after','A genuine local improvement with a limited scope','Left: source photograph. Centre: rejected 50k normals-only rebuild. Right: the new 50k full rebuild shown from the same original camera. The obstruction is removed. That is meaningful progress, but the new result still has softer detail than the photograph and this camera does not test dollhouse usability. '+C('pilot','visibility','matched'),maxh=250)
    P('An explicit-pinhole, scale-only, cross-view-validated bathroom pilot passed before the full rebuild. The full capture then used that combined workflow from step zero. Materializing camera views, validating geometry, densifying the seed, restricting normals and changing optimization were combined interventions. I did not run a single-variable causal study. It would be incorrect to assign all improvement, or all remaining blur, to one of them.')
    P('The new workflow did not implement Gaussian cutaway/overview, a clean architectural surface proxy, a display-fidelity audit across LoD and packed-storage variants, or a user-accepted navigation review. It also did not fix the old C++ mask-drop/per-vertex mesh-carving behavior; it bypassed mesh extraction for this delivery. '+C('viewer','review'))

    H('13. Issue ledger: confirmed facts and hypotheses',new=True)
    T(['Issue','Evidence / confidence','Practical consequence'],[
        ['Missing dollhouse','Confirmed in viewer branches and hidden controls.','Viewer implementation work is required.'],
        ['Original model is soft','Confirmed in matched original-Ply/source images.','Web packing alone cannot recover the missing detail.'],
        ['Extra public rendering reduction','Confirmed LoD, packed storage and DPR caps. Exact contribution unmeasured.','Need same-pose, same-viewport display ablation.'],
        ['Gaussian RGB resampling','Confirmed 1200-square supervision; native fisheye data is denser near the front-view centre.','A plausible fine-detail bottleneck, requiring an isolated test.'],
        ['Regularization / seed / position trade-off','Confirmed settings; causal blur attribution remains a hypothesis.','Do not blindly increase iterations or disable every constraint.'],
        ['Operator/mirror boundaries','Reviewed masks exist; rough fringe regions remain in some views.','Inspect leaks and false exclusions with coverage checks.'],
        ['SfM framing outliers','Confirmed raw sparse min/max bounds. Current fit is bypassed.','Repair bounds before adding global auto-fit.'],
        ['Off-path consistency','Latest screenshot pose unknown; extreme native views are weaker.','Reproduce the complaint view and assess a short camera path.'],
        ['Phone compatibility / memory','Actual Fold 7 / iPhone 17 tests are absent.','Desktop/narrow-layout success is insufficient.'],
    ],[123,199,d.CW-322])
    P('Other unresolved candidates include lens-rim calibration error, remaining rolling-shutter/stabilization effects, varying exposure and per-view appearance optimization. The retained evidence does not establish any one of these as the dominant current failure. They should not become unsupported explanations that displace the confirmed viewer defects or source-resolution choices.')

    H('14. Recommendations and a bounded plan',new=True)
    H('Stage A - restore the expected product behavior',2)
    P('Make dollhouse / overview the Osmo entry experience, matching the preferred iPhone Lite interaction. Use robust occupied-room bounds and an explicit global orbit target. Provide Top, fit/reset, rotate and an interior Walk option with consistent meanings across models. Make Reset mode-aware and avoid an abrupt FOV jump when leaving a calibrated preset. These are proposed changes; this report does not deploy them.')
    P('Prototype reversible Gaussian ceiling/exterior visibility using the renderer\'s supported edit mechanisms, or a lightweight architectural mesh proxy with the Gaussian used for interior appearance. Preserve the full-height cabinet, window and door geometry. Select structural ceiling regions by validated geometry/room regions; do not revive a blanket low horizontal cut. Test the clipping behavior under LoD because a coarse primitive can span a cut boundary. (R1)')
    H('Stage B - isolate display loss before another training run',2)
    T(['Controlled comparison','Keep fixed','Question answered'],[
        ['All-source original PLY vs all-source SOG','Exact camera, viewport, SH, sorting and splat storage.','Transport loss at the actual complaint scale.'],
        ['SOG with extSplats on / off','LoD off; same camera and viewport.','Runtime packed-storage error separate from SOG packing.'],
        ['All-source vs 2M vs 750k LoD','Same file, camera, DPR and sort.','Detail cost of the deployed draw budgets.'],
        ['DPR cap / viewport change','Match field of view and crop location.','Display-resolution loss, not camera movement.'],
        ['Sorting / filter option change','Same points and projection.','Rendering contribution; avoid disguising geometry failure.'],
    ],[150,185,d.CW-335])
    P('These tests should use the latest screenshot\'s reproduced camera if available, plus the fridge, floor/fan, bathroom and doorway views. Save full-viewport images and consistent detail crops. Keep a controlled metric for comparison, but require a visible improvement rather than a primitive-count certificate.')
    H('Stage C - a small, causal processing experiment',2)
    P('Freeze the audited masks and cameras for the first comparison. On a representative living/bathroom subset, compare 1200-square training with a higher angular sampling target, while holding the primitive budget and optimization recipe constant. Confirm that the higher-resolution input actually supplies additional source detail, rather than upsampling the same data. Only then vary the strongest regularization/position constraints one group at a time. Use a fresh initialization for each variant; preserve the baseline and exact commands.')
    P('Inspect mask boundaries and lens-rim views separately. A larger operator mask should be judged by both reduced foreground leakage and retained background support. Evaluate views excluded by time, all tested paths and the latest user view. Stop the full-scene rerun cycle until a small pilot gives a clear visual gain.')
    H('Stage D - choose the right architectural representation',2)
    P('If a Gaussian cutaway alone cannot give a coherent overview, test a surface-oriented or hybrid representation. The 2DGS research explicitly targets surface consistency and mesh reconstruction. It is a candidate for a controlled prototype, not a method already run here or a guarantee of success on this footage. A validated-depth mesh/planar proxy also needs foreground-aware fusion and hole/occlusion checks. The old circular distance-to-holed-probe filter must not become its acceptance rule. (R3)')
    H('Stage E - real-device sign-off',2)
    P('Test the selected final viewer on the actual Fold 7 and iPhone 17, including cold loading, visible progress, decode memory, touch orbit/pinch/pan, cancel/retry, orientation changes and background/return. Prebuilt/paged LoD is worth evaluating if it improves startup and memory while respecting the total download budget. Physical-device results remain pending; the user previously said they would check later. This report does not ask them to repeat that answer. (R2)')

    H('15. Proposed acceptance criteria',new=True)
    P('These are proposed engineering gates for the next implementation. They are not claims about completed work, and numerical limits should support, not replace, the user\'s acceptance of the experience.')
    T(['Requirement','Concrete review','Pass condition'],[
        ['Dollhouse first','Open Osmo; Top; orbit; rotate; reset.','A coherent whole-room overview is immediately available; controls match the Lite baseline.'],
        ['Structural proportions','Kitchen cabinet, door/window frames and ceiling transition.','Cutaway removes the obstructing shell without cutting tall furniture or shortening openings.'],
        ['Sharpness','Reproduced complaint view and fixed full-viewport detail crops.','Visible source-to-render gap is reduced; no merely larger file or misleading small screenshot.'],
        ['Navigation continuity','Switch Walk / Orbit; leave preset; zoom/pinch; reset.','No unexplained framing jump; predictable target and speed; no accidental stuck input.'],
        ['Coverage','Both bathroom visits plus a continuous path, floors and oblique doorway views.','No return of the opaque shell, large false sheets or new unsupported holes.'],
        ['Delivery / quota','Bare URL, all three choices, cancel and failed response.','No 3D resources before Open; visible failure/recovery; no automatic fallback download.'],
        ['Budget','Measure actual packaged data and optional proxy/LoD files together.','Approximately 50 MB target is respected, or a concrete exception is explained before delivery.'],
        ['Phones','Actual Fold 7 and iPhone 17.','Measured cold loading and controls pass on those devices; desktop emulation is labelled separately.'],
    ],[109,184,d.CW-293])

    H('16. Questions for Gemini Argon / Architect',new=True)
    B('Requirements already resolved by the user','The user wants an experience comparable to iPhone Lite: sharper output, a dollhouse overview and usable controls. Around 50 MB is acceptable. The task is to choose the implementation, not to ask whether those requirements matter.')
    T(['Architectural question','Evidence / decision needed'],[
        ['Cutaway strategy','Renderer-side structural opacity edits, a surface proxy, or a hybrid? Define ceiling/wall selection and furniture preservation, including LoD behavior.'],
        ['Framing and shared controls','Specify robust occupied bounds, global orbit target, overview camera and mode-aware reset. Preserve pose/projection continuity.'],
        ['Primary blur experiment','Which minimum experiment best separates 1200-pixel angular sampling, seed constraints, regularization, appearance optimization and runtime LoD/packing?'],
        ['Geometry backend','Can current validated depths support a coherent surface proxy, or should a surface-oriented Gaussian method be piloted? How will unobserved surfaces and masks be handled?'],
        ['Mobile delivery','Would prebuilt or paged LoD improve real-device behavior without unacceptable total bytes or loss of the overview? Define a quality budget based on physical tests.'],
        ['Evidence still needed','Recover the complaint screenshot\'s camera and renderer settings; define independent withheld-time/path views and an appropriate appearance/geometry check.'],
    ],[146,d.CW-146])
    P('My recommended order is viewer parity first, matched display ablations second, a small processing experiment third, and full-scene rebuilding only after that pilot demonstrates the intended quality. This reduces the risk of spending another long run on the wrong failure mode.')

    H('17. Historical Nikon and Samsung comparison',new=True)
    P('The original three-camera comparison is retained here because it explains the user\'s expectation. The Nikon entry is specifically the Codex 034 version, not another person\'s reconstruction. Nikon and Samsung are no longer active projects; these are retained, dated evidence snapshots, not newly loaded models or current-site choices. '+C('historical'))
    T(['Historical model','Recorded result','What it can establish'],[
        ['Nikon Z8 - Codex 034','576,595 triangles; 41,979,020 bytes; local cooker/counter scope. Source working frames recorded as 8256 x 4644 RAW developments.','It was itself rejected for fragmentation and holes. It cannot be presented as an unqualified successful Nikon reference.'],
        ['Samsung accepted release','Roofless model: 8,569,710 triangles / about 419.8 MB. Source recorded as 2160 x 3840, 7,964 frames / 132.91 s.','Useful coherent-room / dollhouse reference, but much larger, different coverage and processing; defects remained.'],
        ['Current iPhone Fast','1,603,164 triangles / 21.1 MB, derived from the later recovered iPhone model.','The preferred low-bandwidth product baseline. It still contains local reconstruction defects.'],
    ],[142,182,d.CW-324])
    F('historical_nikon','The Codex Nikon 034 reconstruction','Retained original report image. This is the requested Codex version and only a local kitchen section. Its identity and limitations are preserved; it is not substituted with somebody else\'s better Nikon result. '+C('historical_nikon'),maxh=225)
    F('historical_samsung','The retained Samsung dollhouse reference','Accepted historical view with more retained mesh geometry. Image/date/model differences prevent an equal-budget, same-scene camera ranking. The comparison is useful for expected overview behavior. '+C('historical_samsung'),maxh=230)

    H('18. Delivery status versus product acceptance',new=True)
    P('The release is technically live at rumah.shizuku.rest in Proxmox LXC 710. Model selection remains explicit, with iPhone Fast, iPhone Full and Osmo. The public pre-choice access-log check recorded only the landing request; one 45,177,102-byte Osmo GET followed the explicit Open action. The iPhone raw/gzip hashes and inherited inodes were preserved. '+C('public'))
    P('A first promotion automatically rolled back because Cloudflare appended its managed robots.txt preamble beyond a strict authored-byte budget. A robots-only exact-prefix verifier fix passed six checks; unchanged site/model files were rehashed and re-promoted. That resolved a deployment-check mismatch. It is unrelated to reconstruction blur or the missing dollhouse feature.')
    P('26 viewer tests and 21 packaging/deployment tests passed before publication. They checked quota gating, format decoding, timeouts, first draw, cancellation and file preservation. They did not require good dollhouse composition, comparable control feel or acceptable large-viewport sharpness. The user\'s rejection supersedes the earlier product-quality implication of the release sign-off. '+C('release_gate','browser','public'))
    B('Honest current status','The model is deployed and loads. The product experience is not accepted. The next action should be a targeted viewer/design and image-quality correction, using the evidence and proposed gates in this PDF.',True)


def appendices(d):
    A=d.A;P=d.P;H=d.H;T=d.table;F=d.fig;C=d.cite
    H('Appendix A. All seven source-view comparisons',new=True)
    P('These are retained real browser renders of the final SOG, with all-source drawing in the controlled review renderer. The source photographs are actual calibrated crops with operator/mirror exclusions. They are not generated images. The public viewer uses a different LoD/storage configuration, detailed in Section 11. '+C('matched'))
    for i,row in enumerate(A['matched']['poses'],1):
        F(f'pair{i}',f'View {i}: {row["timestampSeconds"]:.2f} seconds / {row["split"]}',f'SOG vs source: {row["packedVsSource"]["psnrDb"]:.2f} dB. SOG vs original Gaussian: {row["packingVsNative"]["psnrDb"]:.2f} dB. The photographs and renders are aligned at the same registered source camera; this is same-capture appearance evidence, not surveyed geometry.',maxh=265)
    H('Appendix B. Lowest-scoring held-out views',new=True)
    P('The six lowest valid-pixel PSNR results were selected automatically from all 188 held-out virtual views, then visually reviewed. This avoids showing only the clearest saved cameras. Many low-score views are oblique, near the operator or have limited visible background. Predicted content in black excluded regions is not scored. '+C('native_eval'))
    from PIL import Image
    contact=Image.open(A['images']['worst_eval']['path'])
    for i,row in enumerate(A['worstEval']):
        path=d.HERE/'assets'/f'worst-{i+1}.jpg';contact.crop((0,i*434,1200,(i+1)*434)).save(path,quality=95)
        F(str(path),f'Native eval {row["evalIndex"]}: {row["psnrDb"]:.2f} dB',f'{d.safe(row["name"])}; valid image fraction {row["validFraction"]*100:.1f}%. Left: full GT photograph. Centre: native prediction. Right: the exact scoring keep-mask. No scored pixels were selected by their reconstruction error.',maxh=195)
    H('Appendix C. Complete held-out score table',new=True)
    P('All 188 native evaluation images were matched to source images by RGB similarity, with a unique bijection and full-resolution confirmation. The GT/source maximum RMSE was 0.234/255. Valid pixels use unchanged binary masks. These scores are in the native renderer and do not include the public LoD downgrade. '+C('native_eval'))
    full=Path(A['sources']['native_eval']['path']);rows=json.loads(full.read_text())['rows']
    T(['Eval','Source virtual view','Keep %','PSNR dB','RMSE /255'],[[r['evalIndex'],r['name'],f'{r["validFraction"]*100:.1f}',f'{r["psnrDb"]:.2f}',f'{r["rmse255"]:.2f}'] for r in sorted(rows,key=lambda r:r['evalIndex'])],[35,223,66,80,d.CW-404],small=True)

    H('Appendix D. Executed settings and reproduction contracts',new=True)
    P('The following settings are historical execution evidence. They are included for architectural review, not an instruction to launch compute. Local paths are identified so the exact inputs can be found. No credentials or access tokens are included.')
    H('Exact full-scene Gaussian training argv',2)
    d.STORY[-1].keepWithNext=False
    command=A['trainJob']['command'];lines=[command[0]+' '+command[1]+' '+command[2]];i=3
    while i<len(command):
        if command[i].startswith('--') and i+1<len(command) and not command[i+1].startswith('--'):lines.append(command[i]+' '+command[i+1]);i+=2
        else:lines.append(command[i]);i+=1
    d.code('\n'.join(lines),'Recorded argv; paths and values as executed')
    H('Geometry inference argv',2);d.code('\n'.join(A['geometryJob']['command']),'Recorded MoGe inference argv')
    H('Resolution and coordinate contracts',2)
    T(['Contract','Required interpretation'],[
        ['Native source','3840-square fisheye JPEGs and keep-masks use the same calibration grid.'],
        ['Virtual views','Five proper face rotations per source, masked by physical FOV and foreground; frames below the keep-fraction threshold are omitted. All 452 sources are represented.'],
        ['Frame identity','Both lenses and every virtual view at the same timestamp share train/eval assignment.'],
        ['World identity','The explicit views preserve the audited normalized world; no independent component transform is substituted.'],
        ['Depth','Euclidean ray range; positive scale only; offset exactly zero; uint16 / 1000 in normalized units.'],
        ['Normals','Only pixels supported by validated depth remain normal-valid in trusted guidance.'],
        ['Seed','Training colours only; sparse anchors retained with higher priority; dense candidates need cross-time support.'],
        ['Transport','Original float PLY retained; SOG is quantized; source count and SH degree are preserved.'],
    ],[125,d.CW-125])

    d.orientation('landscape');H('Appendix E. Processing code and viewer branches')
    P('Complete critical processing files are printed below, followed by exact viewer excerpts. Line numbers refer to the preserved source file; a + marks a wrapped display continuation. Third-party libraries, model weights and credentials are excluded. The viewer listing is its pre-bundle source template: build.mjs replaces __MANIFEST__ and the provisional release marker before bundling. Those code-generation tokens are not unresolved placeholders in the live site.','small')
    for rel,title in [
        ('select_frames.py','E1. Adaptive native-frame selection - complete'),
        ('assign_split.py','E2. Timestamp-grouped train/eval split - complete'),
        ('build_explicit_pinhole.py','E3. Explicit calibrated pinhole materialization - complete'),
        ('fit_explicit_depth.py','E4. Positive scale-only depth alignment - complete'),
        ('validate_explicit_depth.py','E5. Cross-time depth validation and dense seed - complete'),
        ('continue_explicit_full.py','E6. Cold-start full reconstruction controller - complete'),
        ('review/pack-sog.py','E7. SOG packing and preservation audit - complete'),
        ('review/production/native-delivery.js','E8. Native format, budget and nonempty-draw policy - complete'),
    ]:d.codefile(rel,title)
    d.codefile('masking/build_masks.py','E9. Native keep-mask composition',150,208)
    d.codefile('review/production/room-viewer.js','E10. Camera, overview and cutaway behavior',17,141)
    d.codefile('review/production/room-viewer.js','E11. Gestures, movement, reset and mode handlers',151,218)
    d.codefile('review/production/room-viewer.js','E12. Zoom / pan, cancellation and hidden native controls',236,274)
    d.codefile('review/production/room-viewer.js','E13. Renderer selection, LoD and startup acceptance',328,405)
    d.codefile('review/production/choice-core.js','E14. Explicit model choice and generation cancellation - complete')
    d.codefile('review/production/chooser.js','E15. Landing-page resource gate - complete')

    d.orientation('portrait');H('Appendix F. Evidence, graph coverage and fingerprints')
    P('The report is self-contained; the following catalogue identifies the local artifacts behind its claims and figures. Hashes bind the inspected files. Original-media checksums mentioned in the narrative are retained import/provenance records, not a claim that the 1.16 GB OSV was newly rehashed during this report. Image crops and comparison sheets are derived, labelled diagnostic figures; underlying source/render hashes are catalogued.')
    g=A['graph'];h=g['healthCounters']
    P(f'Graphify inspected a curated 30-file code snapshot and produced {g["nodes"]} nodes, {g["edges"]} graph edges and {len(g["communities"])} communities. The initial Windows-stdin multiprocessing extraction was discarded and superseded by serial extraction. Graph health reports {h["dangling_endpoint_edges"]} dangling edges and {h["undirected_same_endpoint_collapsed_edges"]} same-endpoint relation collapses. Consequently it is an incomplete static navigation aid, not a runtime proof. Direct source lines and recorded execution artifacts support the branch findings. Its AST pass used 0 external-LLM input/output tokens; that does not describe the token cost of this chat or report authoring. '+C('graph'),'small')
    P('Useful code groups: navigation modes (setMode, home, updateSurface), camera framing (fittedOrbitRadius, orbitCamera, resize), load lifecycle (loadAsset, controlsEnabled, setPhase), delivery policy (nativePolicy) and explicit choice (createChoiceGate). A static connection from loadAsset to these functions does not imply that the mesh and Gaussian branches execute the same behavior.','small')
    for row in A['evidence']:
        P(f'<b>{row["id"]} | {d.safe(row["label"])}</b><br/>{d.safe(row["path"])}<br/>{row["bytes"]:,} bytes | SHA-256 {row["sha256"]}','small')
    H('Appendix G. Primary technical references',new=True)
    refs=[
        ('R1','Spark: Splat RGBA-XYZ SDF editing','https://sparkjs.dev/docs/splat-editing/','Documents region-based per-splat RGBA edits, including plane and box SDFs. Supports a potential cutaway mechanism; it does not supply a finished architectural dollhouse or validate our model.'),
        ('R2','Spark: Level-of-Detail','https://sparkjs.dev/docs/lod-getting-started/','Documents LoD detail/performance trade-offs, packed versus extended storage, prebuilt trees and paged RAD. Platform guidance is a starting point, not a measurement on this user\'s phones.'),
        ('R3','2D Gaussian Splatting for Geometrically Accurate Radiance Fields, SIGGRAPH 2024','https://surfsplatting.github.io/','Surface-oriented Gaussian disks and geometric consistency are relevant to a proxy/mesh pilot. This method was not executed for the current release.'),
        ('R4','Mip-Splatting: Alias-free 3D Gaussian Splatting, CVPR 2024','https://niujinshuchong.github.io/mip-splatting/','Explains smoothing and Mip filtering trade-offs under changes of image sampling. It does not prove that filtering is the dominant source of this model\'s blur.'),
        ('R5','3D Gaussian Splatting for Real-Time Radiance Field Rendering, SIGGRAPH 2023','https://repo-sam.inria.fr/fungraph/3d-gaussian-splatting/','Primary context for sparse-point initialization, anisotropic Gaussian optimization and radiance-field rendering; it is not evidence that a textured architectural mesh or cutaway was built here.'),
    ]
    for key,title,url,note in refs:P(f'<b>{key}. {d.safe(title)}</b><br/><link href="{url}" color="#08787c">{url}</link><br/>{d.safe(note)}','small')
    P('References checked 31 October 2026. External references support mechanisms and proposed experiments. Facts about the actual reconstruction and viewer come from local code, recorded settings, hashes, images and test results.','small')
    H('Terminology used in this report',2)
    T(['Term','Meaning here'],[
        ['Dollhouse','An outside, whole-room architectural overview with a usable ceiling/exterior cutaway.'],
        ['Gaussian / splat','An optimized anisotropic opacity/colour primitive, not a triangle face.'],
        ['LoD','Runtime selection of a lower-detail representation within a draw budget.'],
        ['SfM','Camera pose and sparse-point reconstruction from overlapping images.'],
        ['Depth prior','A learned geometry estimate used as guidance; not measured LiDAR or surveyed truth.'],
        ['Cold start','New optimization from an audited seed rather than a contaminated Gaussian checkpoint.'],
        ['PSNR','Pixel-error metric; does not by itself establish sharpness, geometry quality or control usability.'],
        ['Held out','Excluded from Gaussian appearance training/guidance; the same video may still contribute to SfM camera estimation.'],
    ],[95,d.CW-95])
    P('<b>Final assessment:</b> technical delivery is working; product-quality acceptance failed. The evidence supports a viewer-parity correction and controlled blur diagnosis before another full reconstruction cycle.','small')
