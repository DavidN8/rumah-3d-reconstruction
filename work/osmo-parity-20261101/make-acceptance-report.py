"""Create one self-contained execution and acceptance review, including failures."""
from pathlib import Path
from xml.sax.saxutils import escape
import json,hashlib,io,datetime
from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph,Table,TableStyle,Preformatted
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import ImageReader
W=Path(__file__).resolve().parent;ROOT=W.parent.parent;R=W/'review';Q=R/'qa'
OUT=ROOT/'output/pdf/Osmo_Architect_Mandate_Execution_and_Acceptance_2026-11-01.pdf';OUT.parent.mkdir(parents=True,exist_ok=True)
for name,file in [('Arial','arial.ttf'),('Arial-Bold','arialbd.ttf'),('Arial-Italic','ariali.ttf'),('Consolas','consola.ttf')]:pdfmetrics.registerFont(TTFont(name,'C:/Windows/Fonts/'+file))
pdfmetrics.registerFontFamily('Arial',normal='Arial',bold='Arial-Bold',italic='Arial-Italic',boldItalic='Arial-Bold')
PW,PH=841.89,595.28;M=36;CW=PW-2*M;INK=colors.HexColor('#142836');MUTED=colors.HexColor('#526674');TEAL=colors.HexColor('#087a7c');RED=colors.HexColor('#ad3a39');BG=colors.HexColor('#edf3f5')
c=canvas.Canvas(str(OUT),pagesize=(PW,PH),pageCompression=1);c.setTitle('Osmo 360: architect mandate execution and acceptance review');c.setAuthor('Codex - technical execution evidence')
normal=ParagraphStyle('body',fontName='Arial',fontSize=10.3,leading=14.6,textColor=INK,spaceAfter=7)
small=ParagraphStyle('small',parent=normal,fontSize=8.5,leading=11.4)
pages=[];page_no=0
def load(path):return json.loads(Path(path).read_text())
def paragraph(text,x,y,width=CW,style=normal):
    p=Paragraph(text,style);_,h=p.wrap(width,2000)
    if y-h<42:raise ValueError(f'Page {page_no} text overflow: {text[:80]} at {y-h}')
    p.drawOn(c,x,y-h);return y-h-7
def start(title,subtitle=''):
    global page_no
    if page_no:c.showPage()
    page_no+=1;pages.append(title);c.setFillColor(TEAL);c.rect(0,PH-8,PW,8,fill=1,stroke=0)
    c.setFillColor(MUTED);c.setFont('Arial',8);c.drawString(M,PH-28,'RUMAH / OSMO 360 / EXECUTION REVIEW / 01 NOV 2026')
    c.setFillColor(INK);c.setFont('Arial-Bold',20);c.drawString(M,PH-56,title)
    c.setFillColor(MUTED);c.setFont('Arial',8);c.drawString(M,22,'LOCAL REVIEW ONLY - NOT DEPLOYED - physical Fold 7 and iPhone 17 unverified')
    c.drawRightString(PW-M,22,str(page_no));y=PH-73
    if subtitle:y=paragraph(subtitle,M,y,style=small)
    return y
def img(path,x,y,width,caption=None):
    path=Path(path)
    if not path.is_file():raise FileNotFoundError(path)
    im=Image.open(path);h=width*im.height/im.width
    if y-h<40:raise ValueError(f'Page {page_no} image overflow: {path.name} bottom {y-h}')
    # PDF review copies keep native dimensions with the same high-quality
    # 4:4:4 JPEG encoding for every comparison. Exact PNG evidence stays intact.
    encoded=io.BytesIO();im.convert('RGB').save(encoded,format='JPEG',quality=94,subsampling=0,optimize=True);encoded.seek(0)
    c.drawImage(ImageReader(encoded),x,y-h,width=width,height=h,preserveAspectRatio=True)
    y-=h
    if caption:y=paragraph(caption,x,y-5,width,small)
    return y
def table(headers,rows,widths,y,fontsize=9):
    style=ParagraphStyle('cell',parent=small,fontSize=fontsize,leading=fontsize+3)
    data=[[Paragraph(escape(str(v)),style) for v in headers]]+[[Paragraph(escape(str(v)),style) for v in row] for row in rows]
    t=Table(data,colWidths=widths,hAlign='LEFT');t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),BG),('FONTNAME',(0,0),(-1,0),'Arial-Bold'),('VALIGN',(0,0),(-1,-1),'TOP'),('LINEBELOW',(0,0),(-1,0),.7,TEAL),('LINEBELOW',(0,1),(-1,-1),.3,colors.HexColor('#cfdbdf')),('LEFTPADDING',(0,0),(-1,-1),8),('RIGHTPADDING',(0,0),(-1,-1),8),('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6)]));_,h=t.wrap(CW,2000)
    if y-h<42:raise ValueError(f'Page {page_no} table overflow {y-h}')
    t.drawOn(c,M,y-h);return y-h-12
def code(text,x,y,width):
    style=ParagraphStyle('code',fontName='Consolas',fontSize=8,leading=10.4,textColor=INK)
    p=Preformatted(text,style,maxLineLength=78);_,h=p.wrap(width,2000)
    if y-h<42:raise ValueError(f'Page {page_no} code overflow {y-h}')
    p.drawOn(c,x,y-h);return y-h
scores=load(Q/'scores.json')['rows'];score={(r['model'],r['view']):r for r in scores}
contract=load(W/'input-contract-verification.json');candidate=load(R/'production/candidate.json');bounds=load(W/'occupied-bounds-audit.json');controls=load(R/'controls-verification.json');policy=load(R/'production/build-report.json');poisson=load(R/'poisson-pilot/poisson-audit.json');texture=load(R/'poisson-projected/coherent-filled-report.json')
gate=load(W/'acceptance-gates.json')

y=start('The rebuild ran. The quality gates did not pass.')
y=paragraph('<b>Decision: do not promote this release to rumah.shizuku.rest.</b> The mandated 1600-pixel, 50,000-step rebuild completed and packs to 44.9 MB. It does not show the required clear sharpness leap across the four detail views. The native Gaussian outside cutaway is still visually untidy. Mesh alternatives improve some source-photo detail but retain geometry or texture defects.',M,y)
y=table(['Acceptance requirement','Result','What the evidence means'],[
 ['1. Clean, full-height dollhouse',gate['gates']['dollhouse']['status'],'Overview framing restored; visual surface quality remains unacceptable.'],
 ['2. Top / shell / Walk',gate['gates']['navigationAndShell']['status'],'Navigation behavior passes; a clean reversible visual shell does not yet pass.'],
 ['3. Clear detail sharpness leap',gate['gates']['sharpness']['status'],'Small, mixed Gaussian changes. Texture prototypes are sharper in places but not a clean replacement.'],
 ['4. Download and preservation',gate['gates']['quota']['status'],'44,904,208 model bytes; explicit Open; iPhone files verified unchanged.'],
], [180,85,CW-265],y)
y=paragraph('This document distinguishes implemented features, completed compute, measured observations, and unproven explanations. A successful load, a control test, or a small image-score gain is not a visual acceptance sign-off.',M,y)
y=paragraph('<b>Current production:</b> 20261031-osmo-clean-v1 remains unchanged. All new work is isolated under work/osmo-parity-20261101. Original camera footage, previous checkpoints, and iPhone model files were preserved.',M,y)

y=start('What was executed, in the requested order')
y=table(['Stage','Completed work','Outcome'],[
 ['1 - Scene and controls','Dense occupied bounds, fitted floor/ceiling, 10,000 framing points; Orbit FOV 42; visible Top and See inside; mode-aware Reset; interior Walk; calibrated preset exit.','Behavior passes locally. Native splat cutaway visual quality fails.'],
 ['2 - Display ablations','Eight variants: blur 0 / .05 / .3, extended splats, 2M / 3M / all-source, desktop DPR 1.25 / 2. Full 1920x1080 viewport captures and 600px crops.','Small display differences; no sharpness leap. Local defaults updated, not published.'],
 ['3 - Processing pilots','Matched 8k-step 1200 / 1600 pilots with identical seed, masks, poses, split and budget.','Modest crop gains justified one full test, not acceptance.'],
 ['3 - Full rebuild','Fresh 1600 RGB Lanczos4; 50k steps; cap 3M; requested learning rate, noise, refinement and regularization; appearance-only PPISP / bilateral grid.','Completed in 41m18.641s training. 2,960,980 splats. Failed visual improvement gate.'],
 ['Option B - Surfaces','Official native mesh extraction and photo bake; validated-depth TSDF; chart-consistent source texture; screened Poisson plus SfM anchors and free-space validation.','Comparisons completed. No surface accepted as a complete replacement.'],
 ['Further diagnostics','Matched 8k tests: no geometry guidance / losses; standard 3DGS; exposure corrections disabled; sparse-only initialization.','No clear improvement in all four views. No additional full run based on these results.'],
],[85,445,CW-530],y,8.8)

y=start('Occupied bounds: the 33-unit framing error is fixed')
y=paragraph(f'The framing box now comes from p01-p99 of the validated dense seed, expanded to contain every registered camera center. The Y span is <b>{bounds["heightSpan"]:.4f} scene units</b>, replacing the raw sparse outlier span of 33.03. These are normalized arbitrary units, not surveyed metres.',M,y)
y=paragraph('The floor and upper-ceiling fits use horizontal normal support and robust residual rejection. Floor fit: Y = -0.011291 X - 0.006612 Z - 0.019985 (116,218 inliers; RMSE 0.0431). Ceiling fit: Y = -0.009640 X - 0.019004 Z + 2.433555 (69,680 inliers; RMSE 0.0462). A separate sample of 10,000 occupied points drives camera fitting.',M,y)
img(R/'occupied-bounds.png',M+75,y-5,620,'Dense surface projections and registered camera centers. Green/red show floor and upper ceiling candidates; full-height structures are retained.')

y=start('Dollhouse restoration: behavior versus visual acceptance','Both images are real 1920x1080 Chrome screenshots. A correct Orbit state does not make either rendering a clean accepted dollhouse.')
w=(CW-16)/2
bottom=img(R/'evidence/01-osmo-dollhouse.png',M,y,w,'Fresh Gaussian rebuild: outside framing works, but exposed splats remain spiky and untidy.')
img(R/'poisson-evidence/01-osmo-dollhouse.png',M+w+16,y,w,'Screened-Poisson geometry preview: more continuous layout; rough surfaces remain. Vertex colour here is not the final photo texture.')
y=bottom-10
y=paragraph('<b>Implemented:</b> default Orbit with FOV 42; occupied-room fitting for native splats and meshes; visible Top / See inside; full-height geometry retained; no crude horizontal cabinet-height cut. Native splat modifiers tested ceiling and perimeter classification, then oriented covariance normals and back-face rejection.',M,y)
paragraph('<b>Why this still fails:</b> the Gaussian representation has exposed, elongated primitives outside the photographed path. Covariance normals and perimeter classification are insufficient to make a clean exterior. The surface alternatives are more interpretable but still contain bumps, extrapolated pieces or missing detail.',M,y)

y=start('Top view, reversible shell and navigation')
bottom=img(R/'poisson-evidence/02-osmo-top.png',M,y,w,'Top view of the same untextured surface preview. The view fits the actual apartment, including the corridor and bathroom.')
img(R/'poisson-evidence/03-osmo-roof-restored.png',M+w+16,y,w,'See inside off restores the same geometry using two-sided rendering; no destructive geometry deletion.')
y=bottom-8
paragraph(f'<b>{sum(x["pass"] for x in controls["checks"])} browser checks passed</b> on desktop Chrome / RTX 5080. Tests cover explicit Open, hardware rendering, fitted Orbit state, enabled overview buttons, Top orientation, shell toggle state, Reset in each mode, interior Walk, preset focal continuity, released walking input and browser errors. These are behavior checks. Clean shell appearance and full-height object quality remain visual failures.',M,y)

y=start('Display blur: tested, then bounded local defaults')
y=table(['Setting','Previous release','Local review configuration'],[
 ['Desktop pixel-ratio cap','1.25','2.0'],['Phone pixel-ratio cap','1.0','1.5'],['Screen-space blur','0.3','0.05 (0 was also tested)'],['Extended splats','false','true'],['Desktop draw policy','2M LoD','All source splats; LoD disabled'],['Phone draw policy','750k LoD','1.5M LoD; full decoder memory still required'],
],[200,240,CW-440],y,9)
y=paragraph('Eight matched display variants did not recover the missing detail. Canvas resolution and splat filtering affect presentation, but are not a sufficient explanation for the soft source reconstruction. The 600-native-pixel crop and 600-CSS-pixel screenshot crop are distinct in the evidence. Headless desktop refresh counts are not mobile performance measurements.',M,y)
img(R/'display-ablation/comparison-fridge.png',M+95,y,580)

y=start('Exact processing changes and the correction to the brief')
y=paragraph('<b>Correction:</b> the previous executed configuration already enabled PPISP and the bilateral grid. It also allowed grid corrections for geometry. The tested change makes those corrections appearance-only; it is inaccurate to describe the old run as having no exposure compensation.',M,y)
y=table(['Processing setting','Old full scene','Mandated full rebuild'],[
 ['Virtual RGB / focal pixels','1200 square / 600','1600 square / 800'],['RGB resampling','Bilinear','Lanczos4'],['Training views / eval views','2031 / 188','2031 / 188; same view identities'],['Mean-position learning rate','0.000064 -> 0.0000008','0.00016 -> 0.0000016'],['Position noise','16 -> 0.16','10 -> 0'],['Refinement stop / total steps','35,000 / 50,000','40,000 / 50,000'],['Normal regularization','0.04','0.015'],['Floater suppression','strong','mild'],['PPISP / bilateral grid','Enabled / enabled','Enabled / enabled'],['Grid for geometry','Enabled','Disabled'],['Geometry seed / trusted maps','1,381,699 points / 439','Exact original hashes; 768px maps'],
],[245,235,CW-480],y,8.5)
paragraph('Cold start: no previous Gaussian checkpoint initialization. World transformation is identity in the audited +Y-up frame. Ray depths remain Euclidean ranges with unit scale .001. There is no learned photo synthesis, affine depth offset or new scene normalization.',M,y,style=small)

y=start('Full rebuild: measured results, not a quality sign-off')
y=paragraph('<b>Full run:</b> 50,000 steps, 2,960,980 Gaussians, SH degree 2. Training: 41m18.641s. Native PLY: 485,601,727 bytes. Official SOG pack: <b>44,904,208 bytes</b>, all source splats and SH degree retained.',M,y)
y=table(['Fixed 1920x1080 pose','Old full-frame PSNR','New full-frame PSNR','Old crop PSNR','New crop PSNR'],[[v.title(),f'{score[("old-full",v)]["psnrDb"]:.3f}',f'{score[("new-full-50000",v)]["psnrDb"]:.3f}',f'{score[("old-full",v)]["cropPSNR"]:.3f}',f'{score[("new-full-50000",v)]["cropPSNR"]:.3f}'] for v in ['fridge','fan','dining','bathroom']],[190,145,145,145,CW-625],y,9)
y=paragraph('The masked 188-view native evaluation averages 24.123 dB, versus 24.102 dB previously. Those runs use different native output resolutions, so that tiny numerical difference is not a controlled sharpness improvement. At the same 1920x1080 QA poses, changes are small and mixed. Dining detail is slightly worse. Visual review rejects the required clear leap.',M,y)
y=paragraph('<b>Comparison protocol:</b> four exact camera poses, unchanged intrinsics, direct native-photo remap, original keep masks and fixed 600x600 boxes. No image registration, error-selected masks or post-sharpening. Fridge, fan and dining are source training timestamps; bathroom is appearance-held-out. All SfM cameras were estimated from the same capture, so this is not independent geometric ground truth.',M,y)
paragraph('<b>Input contract:</b> camera R, t and normalized K match exactly; shared unique feature coordinates scale to within 2.3e-13 pixels. All 439 depth/normal maps and the dense seed match their old hashes. Resolution-dependent edge masks admit 3,415 additional sparse observations; repeated point IDs at a few image edges are recorded separately, rather than falsely matched by dictionary row.',M,y,style=small)

for view,label in [('fridge','Fridge stickers'),('fan','Floor fan and vacuum'),('dining','Dining table'),('bathroom','Bathroom tiles')]:
    y=start(label+': original versus full mandated rebuild','Top: full 1920x1080 canvases. Bottom: fixed 600x600 crops, source / old / new. PDF display copies use JPEG94 / 4:4:4 at native pixel dimensions; exact PNGs remain in the project.')
    # Explicit layout leaves enough room for full-view comparisons and crop strip.
    row_top=min(y,514);ww=(CW-16)/2
    by=img(Q/f'old-full-{view}.png',M,row_top,ww)
    img(Q/f'new-full-50000-{view}.png',M+ww+16,row_top,ww)
    c.setFont('Arial',8);c.setFillColor(MUTED);c.drawString(M,by-12,'Old full reconstruction');c.drawString(M+ww+16,by-12,'New 1600px / 50k / 3M-cap reconstruction')
    img(Q/f'newest-{view}.png',(PW-620)/2,by-22,620)

y=start('Option B: official mesh extraction and trusted-depth TSDF')
y=table(['Surface / texture','What ran','Result'],[
 ['Official native mesh + photo bake','Old clean 50k explicit-pinhole checkpoint; grid 384; K=3. Simplified textured mesh under 50 MB; native 3840 photos and first-hit checks.','43.3 MB. Texture/geometry speckling and broken small shapes; rejected.'],
 ['Trusted-depth TSDF','439 train-only ray-range maps; 171 timestamps; .025-unit voxels; no affine alignment; exact GPU plane/range test.','500,005 faces. 10.9 MB photo version; incomplete geometry and grey unsupported texels.'],
 ['Chart-consistent TSDF texture','One primary source photo per UV chart, ranked fallback plus first-hit visibility; original operator/mirror masks; 38 eval images excluded.','10.3 MB. Stickers clearer, but gaps and warped geometry persist. No acceptance.'],
],[165,365,CW-530],y,8.8)
img(Q/'coherent-fridge.png',(PW-665)/2,y,665)

y=start('Screened Poisson: continuity test and its limitations')
y=paragraph(f'The final surface pilot uses <b>{poisson["orientedDepthSamples"]:,} oriented depth samples</b> and <b>{poisson["sparseAnchors"]:,} native SfM anchors</b>. Anchors require error &lt;=1.25 native pixels, at least three distinct training times, proximity to the dense surface and stable nearby normals. Poisson depth 9, point weight 6, confidence weighting; no new transform or low height cut.',M,y)
y=paragraph('Only closures contradicted by five independent trusted timestamps, with no positive surface match, are removed. That trims 2,843 of 1,599,436 faces. The exact shader passes synthetic tests for Euclidean range, rotation/translation, timestamp deduplication, observed-surface protection, invalid maps and behind-camera faces.',M,y)
y=paragraph(f'The surface is reduced to 499,987 triangles with boundary locking (meshopt relative error 0.0003281), then given local planar UV patches. Final photo texture: {texture["textureSize"]} square; {texture["views"]} training photos; {texture["charts"]:,} UV connected components; {texture["supportedFraction"]*100:.2f}% verified source coverage. Packed mesh: 30,150,832 bytes. Unsupported texels remain visibly neutral. An 8K atlas expands to about 256 MiB RGBA memory and is not phone-validated.',M,y)
img(Q/'poisson-fridge.png',(PW-665)/2,y,665)

y=start('Final textured surface: sharper patches, unacceptable scene')
bottom=img(Q/'poisson-photo-overview.png',M,y,w,'Actual photo-textured overview, FOV 42. Geometry and texture defects remain throughout the room.')
img(Q/'poisson-photo-bathroom.png',M+w+16,y,w,'Appearance-held-out bathroom pose. Seams, unsupported areas and displaced surfaces fail the visual gate.')
y=bottom-8
y=paragraph('This is not a hole-free, faithful apartment model. Sharper stickers and grille lines come from real source photos, but surface error and independently selected photo patches create visible misregistration. A global multiview texture-label solution and seam handling would be a different implementation from the tested local chart heuristic. It may reduce some seams, but cannot be assumed to repair incorrect geometry.',M,y)
paragraph('A real implementation struggle: PyMeshLab exported non-unit vertex normals (lengths up to 2*pi); the UV input now normalizes them and rejects zero-area triangles. The automatic conformal atlas remained slow even after correction and triangle reduction, so it was stopped. Local planar patch projection plus UV-only packing finished in 14.875 seconds; the photo bake took 80.516 seconds. These are issues in the new mesh experiment, not a diagnosis of the old Gaussian blur.',M,y,style=small)

y=start('Four further training diagnostics did not resolve the blur')
y=table(['8k-step pilot','Variable isolated','Observed result'],[
 ['RGB-only Mip','All depth/normal loading and geometry loss weights disabled.','No substantial fridge-detail leap.'],['RGB-only standard 3DGS','Same RGB-only input; primitive changed from Mip to standard 3DGS.','No substantial leap.'],['No appearance correction','Guided 1600 recipe; PPISP and bilateral grid both off.','No substantial leap; exposure compensation alone is not the fix.'],['Sparse initialization','Identical RGB-only 3DGS pilot; sparse train-only feature seed replaces the dense depth-derived seed.','Mixed: crop PSNR fridge +0.263, fan -0.263, dining -1.886, bathroom +1.025 dB; no all-view leap.'],
],[190,360,CW-550],y,9)
y=paragraph('These are small controlled diagnostics, not proof that each technique is universally ineffective. They show that another full run based solely on these changes is not supported by the present evidence. The seed, limited pilot training duration and fixed camera solution remain shared constraints.',M,y)
img(Q/'appearance-test-fridge.png',(PW-665)/2,y,665)

y=start('Quota, preservation and physical-device limits')
y=paragraph('<b>Quota gate passes for the staged Gaussian asset.</b> The landing page contains three choices and an explicit Open button. Merely loading the page, selecting a card or using a deep link does not fetch the 3D model or start the renderer. Unit tests, browser request timing and the local package audit independently check this behavior. Packaging/deployment has not been run.',M,y)
y=table(['Asset','Verified bytes','SHA-256'],[[p['model'],str(p['bytes']),p['sha256']] for p in contract['iphoneModels']]+[['New Osmo SOG','44,904,208',candidate['sha256']]],[95,105,CW-200],y,8)
y=paragraph('All 34 preserved original source files match their saved hashes. The iPhone camera metadata and model metadata also match. Raising viewer DPR changes local display behavior, not the underlying iPhone model bytes. The original source and public release were not overwritten.',M,y)
y=paragraph('<b>Physical phones remain unverified.</b> Desktop Chrome / RTX 5080 checks do not establish Fold 7 or iPhone 17 GPU memory, thermal behavior, touch ergonomics or Safari memory limits. A compressed file below 50 MB can still decode into hundreds of megabytes. No claim of successful physical phone operation is made.',M,y)
paragraph('The 44.9 MB Gaussian plus the 10.3 MB TSDF surface would total more than 50 MB if both downloaded for one selection. That combination is not an eligible hybrid under the mandate. An eventual hybrid must measure the total assets fetched, including any overview proxy, rather than checking each file separately.',M,y)

y=start('What the experiments establish - and what they do not')
y=paragraph('<b>Established:</b> the framing and control regressions were real and are fixed locally. The old sparse bounds were invalid for room framing. The exact requested processing recipe is insufficient to recover the required detail. Display settings and SOG packing are not a sufficient explanation. Source-photo baking can recover finer stickers than the Gaussian render, but surface defects prevent using the tested mesh as the final product.',M,y)
y=paragraph('<b>Not established:</b> that the camera cannot produce a good reconstruction; that 360 footage is inherently inferior; that a nonzero rig baseline is wrong; that changing one learning rate or enabling exposure compensation solves this data; or that one global mean reprojection score proves subpixel photometric agreement in every object region.',M,y)
y=paragraph('<b>Recommended next experiment:</b> use the existing fridge/fan region for a calibrated multiview alignment audit. Measure repeated edge positions versus viewing angle, lens radius and capture time, with operator/mirror masks fixed. Compare sparse-feature reprojection with dense photometric edge agreement. Test shared physical-camera/rig refinement if the residuals warrant it; do not independently optimize overlapping virtual faces as unrelated cameras.',M,y)
y=paragraph('If dense camera alignment is sound, compare a small region against a second established Gaussian training implementation, from the same photographs and camera solution. This would distinguish current trainer/primitive behavior from camera/calibration inconsistency. Also compare an independently reconstructed multiview surface with the monocular-depth-derived surface; the present Poisson and TSDF variants inherit the same depth uncertainty.',M,y)
paragraph('<b>Stop/go condition:</b> require a visible improvement in all four fixed detail crops and a clean, reversible full-height dollhouse before another public promotion. Reuse the same evaluation masks and poses. No larger file, longer training run or higher score alone is a substitute. This recommendation is a next controlled experiment, not a newly diagnosed root cause.',M,y)

y=start('Implementation references: camera fit and navigation')
left="""// Illustrative navigation logic.
// Actual implementation: room-viewer.js
function home() {
  if (!ready) return;
  if (mode === 'orbit') setMode('orbit');
  else walkHome();
}

// Orbit entry, shared by mesh and Gaussian:
camera.fov = 42;
orbit.target = centerOfOccupiedBounds;
orbit.theta = .7;
orbit.phi = .85;
orbit.radius = fittedOrbitRadius();
seeInside = true;
orbitCamera();

// Walk entry from an exterior orbit:
walkHome();              // interior start pose
seeInside = false;      // complete shell

// Preset exit preserves pixel focal length:
const scale = viewportHeight / imageHeight;
const freeFy = recordedFy * scale;
camera.fov = radToDeg(
  2 * Math.atan(canvasHeight / (2 * freeFy))
);
// Off-center principal point also retained.
"""
right="""// Fitted radius: every occupied sample matters.
for each occupied point p:
  relative = p - boundsCenter
  depth = dot(relative, orbitDirection)
  radius = max(radius,
    depth + 1.12 * abs(dot(relative, right))
                  / (tan(fov/2) * aspect),
    depth + 1.12 * abs(dot(relative, up))
                  / tan(fov/2))

// Mesh See inside:
material.clippingPlanes = [];
material.side = seeInside
  ? THREE.FrontSide : THREE.DoubleSide;

// Native Gaussian delivery policy:
desktop: all source splats, LoD disabled
phone:   LoD budget 1,500,000
both:    extSplats true, blurAmount .05
DPR cap: desktop 2.0 / phone 1.5

// Quality package gate (all are mandatory):
cleanFullHeightDollhouseAccepted
topAndReversibleShellAccepted
fourDetailSharpnessLeapAccepted
totalModelDownloadWithin50MB
zeroModelBytesBeforeOpen
iphoneHashesPreserved
"""
code(left,M,y,365);code(right,M+397,y,365)

y=start('Evidence map and reproducibility')
y=paragraph('Paths below are relative to <b>work/osmo-parity-20261101/</b> in the project. The PDF contains JPEG94 / 4:4:4 display copies at native pixel dimensions. Scores use the exact original PNGs, not the PDF copies. Original 1920x1080 PNGs, requests and machine-readable tests remain in the project. No ZIP is needed.',M,y)
y=table(['Evidence','File or folder'],[
 ['Bounds and fitted structural planes','occupied-bounds-audit.json; review/occupied-cameras.json'],['Calibrated reference export','review/export-clean-cameras.py; review/calibrated-occupied-cameras.json'],['Input identity, guidance, iPhone hashes','input-contract-verification.json'],['Eight display variants','review/display-ablation/measurements.json; comparison-*.png'],['Exact full training command and log links','full-sharp-request.json; highres-preparation.json'],['Four fixed poses and 600px crop scores','review/qa/metadata.json; review/qa/scores.json; newest-*.png'],['Browser navigation / request checks','review/controls-verification.json; review/evidence/'],['Mesh / TSDF / Poisson provenance','review/mesh-pilot/; review/tsdf-pilot/; review/poisson-pilot/'],['Acceptance decision / deployment refusal','acceptance-gates.json; review/production/release-approval.json'],
],[250,CW-250],y,8.4)
y=paragraph('Final Poisson photo texture and audit: <b>review/poisson-projected/</b>. Additional diagnostic: <b>sparse-init-pilot.py</b>. Pre-choice / phone draw-policy evidence: <b>review/choice-and-phone-policy-verification.json</b>. Local file and failed deployment-gate audit: <b>local-package-audit.json</b>.',M,y,style=small)
y=paragraph('Primary implementation references: <link href="https://sparkjs.dev/docs/splat-mesh/" color="#087a7c">Spark SplatMesh</link>; <link href="https://sparkjs.dev/docs/spark-renderer/" color="#087a7c">Spark renderer</link>; <link href="https://pymeshlab.readthedocs.io/en/latest/filter_list.html#generate-surface-reconstruction-screened-poisson" color="#087a7c">PyMeshLab screened Poisson filter</link>. The chart-based photo selection here is a local heuristic; it is not the full graph-cut algorithm from the <link href="https://github.com/nmoehrle/mvs-texturing" color="#087a7c">MVS-Texturing reference implementation</link>.',M,y,style=small)
paragraph('<b>Final status:</b> staged viewer changes and actual rebuilds are complete; acceptance is not. The current release remains public. This record deliberately retains failed results so the next architectural decision can be based on evidence rather than another assumed fix.',M,y)
c.save()
audit={'file':str(OUT),'pages':page_no,'bytes':OUT.stat().st_size,'sha256':hashlib.sha256(OUT.read_bytes()).hexdigest(),'titles':pages,'visualQA':'pending'};(W/'pdf-audit.json').write_text(json.dumps(audit,indent=2));print(json.dumps(audit,indent=2))
