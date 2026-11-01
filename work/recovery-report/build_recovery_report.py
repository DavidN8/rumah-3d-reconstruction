from pathlib import Path
import json,hashlib,shutil,zipfile,html
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4,landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph,Table,TableStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import ImageReader
from PIL import Image

WORK=Path(__file__).parent
ROOT=WORK.parents[1]
OUT=ROOT/'outputs'
IP=Path(r'C:/Users/bombe/OneDrive/Documents/ChatGPT/Ruang Kamare/roomscan-reconstruction/data/20261027_IPHONE_WIDE')
RUN=IP/'recovery-v2'
PACK=WORK/'reference_pack'
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
MANUAL=read(RUN/'analysis/architect-review.json')
STAGE=MANUAL['display_stage']
V=read(RUN/f'analysis/{STAGE}-verification.json')
RAW=read(RUN/'analysis/allviews-raw-verification.json')
FAST=read(RUN/'analysis/allviews-fast-packed-verification.json')
INTEGRITY=read(RUN/'analysis/full-native-integrity.json')
DEPTH=read(RUN/f'analysis/verification-{STAGE}/depth-and-hole-checks.json')
CONTROLS=read(RUN/f'analysis/verification-{STAGE}/fixed-controls-check.json')
BRIDGE=read(RUN/'analysis/wide-bridge.json')
COVERAGE=read(RUN/'analysis/all-usable-coverage.json')
DEV=read(RUN/'analysis/allviews-fast-deviation-summary.json')
OLD=ROOT/'work/report/reference_pack'
W,H=landscape(A4);M=33;CW=W-2*M;G=20;COL=(CW-G)/2
INK=colors.HexColor('#173143');MUTED=colors.HexColor('#526A78');TEAL=colors.HexColor('#147C86');LIGHT=colors.HexColor('#EEF4F6');LINE=colors.HexColor('#C9D8DF')
for n,f in [('Body','calibri.ttf'),('Bold','calibrib.ttf'),('Mono','consola.ttf')]:pdfmetrics.registerFont(TTFont(n,'C:/Windows/Fonts/'+f))
pdfmetrics.registerFontFamily('Body',normal='Body',bold='Bold',italic='Body',boldItalic='Bold')
styles={k:ParagraphStyle(k,fontName=f,fontSize=s,leading=l,textColor=col,spaceAfter=6) for k,f,s,l,col in [('body','Body',11,14.3,INK),('small','Body',9.3,12.1,MUTED),('h2','Bold',15.5,19,TEAL),('h3','Bold',11.6,15,INK),('tiny','Body',8.2,10.5,MUTED),('cover','Bold',28,32,INK),('cell','Body',9.2,11.8,INK),('head','Bold',9.2,11.8,colors.white)]}
OUT.mkdir(exist_ok=True);PACK.mkdir(parents=True,exist_ok=True)
PDF=OUT/'Gemini_Argon_iPhone_Recovery_Verification_2026-10-27.pdf'
c=canvas.Canvas(str(PDF),pagesize=(W,H),pageCompression=1);c.setTitle('iPhone recovery execution and verification for Gemini Argon');c.setAuthor('Codex');page=0;layout=[];titles=[]
def p(text,x,y,w=CW,style='body'):
    a=Paragraph(text,styles[style]);_,h=a.wrap(w,H)
    if y-h<38:raise RuntimeError(f'Page {page} text overflow: {text[:75]}')
    a.drawOn(c,x,y-h);layout.append({'page':page,'kind':'text','bottom':y-h});return y-h-6
def top(title,sub=''):
    global page
    if page:c.showPage()
    page+=1;titles.append(title);c.setFillColor(TEAL);c.rect(0,H-7,W,7,fill=1,stroke=0)
    c.setFont('Bold',8);c.setFillColor(MUTED);c.drawString(M,H-28,'GEMINI ARGON / ARCHITECT | IPHONE WIDE RECOVERY | 27 OCT 2026')
    y=p(title,M,H-40,CW,'cover' if page==1 else 'h2')
    if sub:y=p(sub,M,y,CW,'small')
    c.setStrokeColor(LINE);c.line(M,30,W-M,30);c.setFont('Body',8);c.setFillColor(MUTED);c.drawString(M,18,'Local reconstruction evidence. Approximate scale; visible defects and failed gates are disclosed.');c.drawRightString(W-M,18,str(page))
    c.bookmarkPage('p'+str(page));c.addOutlineEntry(title,'p'+str(page));return y-4
def img(path,x,y,w,maxh):
    path=Path(path);iw,ih=Image.open(path).size;h=min(maxh,w*ih/iw);rw=h*iw/ih
    if y-h<38:raise RuntimeError(f'Page {page} image overflow: {path.name}')
    c.drawImage(ImageReader(str(path)),x+(w-rw)/2,y-h,width=rw,height=h);layout.append({'page':page,'kind':'image','file':str(path),'bottom':y-h});return y-h-8
def crop(path,box,x,y,w,maxh):
    # PDF clipping only. Original screenshots in the evidence pack are unchanged.
    iw,ih=Image.open(path).size;l,t,r,b=box;h=min(maxh,w*(b-t)/(r-l));rw=h*(r-l)/(b-t);scale=rw/(r-l);xx=x+(w-rw)/2
    c.saveState();clip=c.beginPath();clip.rect(xx,y-h,rw,h);c.clipPath(clip,stroke=0);c.drawImage(ImageReader(str(path)),xx-l*scale,y-h-(ih-b)*scale,iw*scale,ih*scale);c.restoreState();layout.append({'page':page,'kind':'image-clip','file':str(path),'bottom':y-h});return y-h-7
def table(rows,x,y,widths):
    cells=[[Paragraph(str(v),styles['head' if i==0 else 'cell']) for v in row] for i,row in enumerate(rows)]
    t=Table(cells,colWidths=widths);t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),TEAL),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,LIGHT]),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),7),('RIGHTPADDING',(0,0),(-1,-1),7),('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6),('LINEBELOW',(0,0),(-1,-1),.4,LINE)]));_,h=t.wrap(sum(widths),H)
    if y-h<38:raise RuntimeError(f'Page {page} table overflow')
    t.drawOn(c,x,y-h);layout.append({'page':page,'kind':'table','bottom':y-h});return y-h-10
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def mb(n):return f'{n/1e6:.1f} MB'
def flag(x):return 'PASS' if x else 'FAIL'
def heading(text,x,y,w=COL):return p(text,x,y,w,'h3')

y=top('iPhone reconstruction recovery','Execution record, actual browser comparisons, remaining defects and decisions requested. Companion to the original three-model architecture report.')
left=p('<b>'+html.escape(MANUAL['status'])+'</b>',M,y,COL)
left=p(html.escape(MANUAL['summary']),M,left,COL)
left=heading('What was rebuilt',M,left)
left=p('Fresh metric-depth inputs and corrected dense seeds; a 40k-step kitchen pilot; one 50k-step living/corridor/bedroom component. One proper similarity per independent COLMAP component. No separate bedroom floor tilt.',M,left,COL)
left=p('An additional full-coverage living run restores all 311 usable views after the first run unnecessarily withheld fixed comparison photos and interval-evaluation frames. Both runs and their source datasets remain preserved.',M,left,COL)
right=img(RUN/f'analysis/verification-{STAGE}/after-overview.png',M+COL+G,y,COL,270)
right=p(f'<b>Primary full native delivery:</b> {V["mesh"]["triangles"]:,} triangles / {mb(V["mesh"]["bytes"])}. Two embedded 8K JPEG textures. Every native triangle is retained; no post-extraction simplification.',M+COL+G,right,COL,'small')
p('Read the eight source comparisons and the gate table before interpreting any headline triangle count, training metric or screenshot as acceptance.',M,80,CW,'small')

y=top('Execution against the architectural mandate','Completion of computation is separate from acceptance of the resulting geometry.')
rows=[['Stage','What was actually done','Outcome / limit'],['1. Audit and components','Reviewed registered doorway windows; excluded 22 blurred frames. Replaced three temporal zones with two original SfM components.','No confirmed active door swing in the registered contacts. The discarded wider join estimate did not satisfy three-plane constraints.'],['2. Geometry and seeds','Fresh 501-view metric-depth inference; depth-grid intrinsics and RGB sampling matched. Observed sparse tracks align depth in the shared scene frame.','150k kitchen / 300k living seeds; projections checked. Learned depth and scale remain approximate.'],['3. Kitchen pilot','High quality, 40k steps, cap 2.5M; native 0.5 merge, default 512 grid, 8K JPEG90.','Visible counter/appliance improvement passed the pilot continuation gate. Narrow wall perforations and soft small objects remain.'],['4. Unified living component','High quality, 50k steps, cap 3M. No internal temporal seam or bedroom tilt. Repeated once with all 311 usable views after correcting the evaluation split.','See the fixed views. A remaining defect is not declared resolved merely because the split was removed.'],['5. Delivery and verification','HTTP and embedded offline review; all eight source views, dollhouse, depth layers, compaction ablation, actual browser controls.','Primary delivery state: '+MANUAL['primary_delivery_state']]]
y=table(rows,M,y,[111,337,CW-448]);p('The original checkpoints, raw meshes, older deliverable and protected Nikon/Samsung assets were preserved. Historical temporal exporters now reject accidental reuse.',M,y,CW,'small')

y=top('The three models: correct provenance retained','Historical reference images are reused byte-for-byte. No new Nikon or Samsung reconstruction or rendering was run.')
cards=[('iPhone - full native rebuild',RUN/f'analysis/verification-{STAGE}/after-overview.png',f'{V["mesh"]["triangles"]:,} triangles / {mb(V["mesh"]["bytes"])}. Two original components, apartment scope. Native geometry selected by the user; remaining surface defects are disclosed.'),('Nikon Z8 - Codex 034',OLD/'images/F04-codex-nikon-034.png','Historical native-camera-kitchen-034: 84 frames, 24k steps, 576,595 triangles / 42.0 MB raw. Quality rejected; a small kitchen test, not a complete apartment.'),('Samsung - accepted release',OLD/'images/F03-samsung-accepted.png','Accepted bedroom/bathroom release: 9,080,740 full triangles; roofless overview 8,569,710 / 419.8 MB. Preserved geometry with known occlusion gaps and uncalibrated physical scale.')]
cw=(CW-24)/3
for i,(title,path,text) in enumerate(cards):
    xx=M+i*(cw+12);yy=p(title,xx,y,cw,'h3');yy=img(path,xx,yy,cw,205);p(text,xx,yy,cw,'small')
p('These are different scenes, capture scopes, source resolutions and processing histories. This comparison supports a processing-quality discussion, not a camera-brand ranking. The Nikon raw hash begins fc123e86 and its display wrapper hash begins b87af585, as pinned in the original evidence pack.',M,106,CW,'small')
p('The complete original 28-page report, provenance JSON and historical image references are included with the new evidence pack.',M,64,CW,'small')

y=top('Input corrections and what they establish','The pilot changes several coupled factors; its improvement does not isolate a single cause.')
left=heading('Depth, camera and seed contract',M,y)
left=p('The fresh MoGe maps use a 598 x 1064 grid. Focal lengths and principal point are scaled from the original 1080 x 1920 calibration separately in x and y. Seed RGB is sampled on the same grid.',M,left,COL)
left=p('Depth is explicit millimetre z-depth. Each reliable map is robustly aligned to this image\'s associated, observed sparse tracks in the transformed component frame. Unreliable or non-positive fits are omitted from depth supervision and seeding; RGB and normals remain available.',M,left,COL)
left=p('Proper rotations have determinant +1. Geometry and all 501 camera poses share the same component-level similarity. The final matrices and projected sparse tracks are checked independently of screenshots.',M,left,COL)
left=p('The legacy single-K seed entry point rejects a merged, two-calibration model. The retired zone-0/1/2 commands cannot silently overwrite the component reconstruction.',M,left,COL)
left=p('Native recipe: merge 0.5, default grid 512, four bisection iterations, carve-k 3, hole ratio 0, hole edge limit 64, floater minimum 50 faces, 8192 texture and JPEG90. The edge rule still fills small holes even when the ratio is zero; no manual wall patch was added.',M,left,COL,'small')
right=img(RUN/'analysis/allviews-proj_check.jpg',M+COL+G,y,COL,335)
p('Four source/seed overlays: kitchen 903/999 and unified component 3606/4297. This is a projection sanity check, not an independent measurement of true surfaces.',M+COL+G,right,COL,'small')

y=top('Coverage correction and training record','The initial recovery accidentally introduced two layers of holdouts. This is documented as an implementation issue.')
y=table([['Run','Loaded views / contributing train views','Settings and elapsed training'],['Kitchen pilot','166 loaded; 152 train / 14 engine eval. Eight blur exclusions plus two external fixed-view holdouts.','High; 40k; cap 2.5M; full-resolution phase after 30%. '+f'{read(RUN/"analysis/zone-kitchen-training.json")["elapsed_seconds"]/60:.2f} min.'],['First unified living run','305 loaded; 279 train / 26 engine eval. Fourteen blur exclusions plus six external fixed-view holdouts.','High; 50k; cap 3M. '+f'{read(RUN/"analysis/zone-living-bedroom-training.json")["elapsed_seconds"]/60:.2f} min.'],['Full-coverage living run','311 usable views all train; 14 audited blur exclusions. No fixed-view or interval holdout.','High; 50k; cap 3M; fresh corrected 300k seed. '+f'{read(RUN/"analysis/zone-living-bedroom-allviews-training.json")["elapsed_seconds"]/60:.2f} min.'] ],M,y,[149,337,CW-486])
y=p('Why repeat the living run: frame 1398 is near the component boundary. Withholding it, together with the engine\'s interval split, weakened coverage exactly where the first recovery retained a severe foreground sheet. The repeat tests that concrete hypothesis; improvement is judged from the new mesh, not assumed.',M,y,CW)
y=p('All-coverage living comparisons are in-sample delivery checks. The SfM poses also use the original full registered image set. Neither the initial holdouts nor this repeat constitute independent capture or surveyed validation.',M,y,CW)
y=p('Shared training settings: resolution divisor 1; progressive full resolution at 30%; SH degree 3 / regularization 0.001; maximum world size 0.12 approximate metres; depth weight 0.05 and normal weight 0.02; z-depth rather than ray depth. Orientation, centering and automatic pose scaling are disabled. Refinement stops 10k steps before the run ends.',M,y,CW,'small')
p('GPU pacing was disabled and 16 CPU threads were configured. No new capture was requested. The raw training and native extraction records preserve exact commands and elapsed times.',M,y,CW,'small')

y=top('Dollhouse comparison','Before: restored pre-rebuild export. After: the reviewed new derivative. Full geometry remains available; roof cutaway uses an exact horizontal clipping plane.')
yy=img(RUN/f'analysis/verification-{STAGE}/before-overview.png',M,y,COL,300);p('BEFORE - previous restored export, 1,082,185 triangles / 60.8 MB.',M,yy,COL,'small')
yy=img(RUN/f'analysis/verification-{STAGE}/after-overview.png',M+COL+G,y,COL,300);p('AFTER - '+html.escape(MANUAL['overview_finding']),M+COL+G,yy,COL,'small')
p('Visible room coverage and furniture coherence must be assessed together with the interior comparisons. A dollhouse can conceal a foreground sheet or holes behind the bed. Cutaway is a viewing operation; source geometry is retained in the full model.',M,106,CW)

for i,view in enumerate(MANUAL['views'],1):
    y=top(f'{i:02d} / {view["label"]} - source frame {view["frame"]}',html.escape(view['finding']))
    col=(CW-24)/3
    for k,label in enumerate(['BEFORE - previous export','AFTER - reviewed rebuild','SOURCE - original frame']):p(label,M+k*(col+12),y,col,'h3')
    yy=y-23
    for k,label in enumerate(['before','after']):crop(RUN/f'analysis/verification-{STAGE}/{label}-{i:02d}.png',(121,112,599,962),M+k*(col+12),yy,col,365)
    img(IP/f'frames/frame_{view["frame"]:07d}.jpg',M+2*(col+12),yy,col,365)
    p('Actual WebGL screenshot regions, with the original photo once at right. Full uncropped screenshots are attached. Before/after use the same source-frame identity and each model\'s consistent transformed pose; raw/compact ablations use identical cameras.',M,74,CW,'tiny')

y=top('Kitchen join: wider matching did not establish precision','A rejected candidate is retained as evidence, not silently promoted.')
left=p('The known switch-plate pair served as a positive control. The initial higher-resolution confidence threshold rejected even this control, so wider matching was rerun at a calibrated resolution and threshold.',M,y,COL)
left=p('Across 32 unique wider pairs, only 32 geometrically filtered matches remained: no horizontal-floor matches, three wall-x matches spanning about 6.4 cm, and 29 wall-z matches spanning about 15.7 cm. This does not provide three orthogonal, spatially distributed constraints.',M,left,COL)
left=p('The candidate fit had a small matched-point residual but a held-out 90th-percentile residual near 18.8 cm. Its rotation/translation update was rejected. The previous approximate kitchen join is retained, and exact scale or lever-arm alignment is not claimed.',M,left,COL)
right=img(RUN/'analysis/wide-bridge-witness.jpg',M+COL+G,y,COL,270)
p('Normal groups derive from learned-depth neighbourhoods. They are diagnostic labels, not surveyed wall planes. A single global similarity is still applied per original component.',M+COL+G,right,COL,'small')

y=top('Doorway defect: component ablation','This check distinguishes internal reconstruction error from an overlap between the two independent components.')
left=p(html.escape(MANUAL['seam_finding']),M,y,COL)
left=p('In the first recovery, hiding the kitchen left the foreground sheet at frame 1398 unchanged. The kitchen-only render showed mostly background there. Therefore the main defect at this view belonged to the living mesh itself; clipping kitchen triangles would not repair it.',M,left,COL)
left=p('A global nearest-camera ownership crop was not reused. It previously deleted valid floors and walls. A precise doorway-plane/occlusion cleanup still requires a defensible plane and a matched-camera ablation proving that no valid structure is lost.',M,left,COL)
right=img(RUN/'analysis/seam-ablation/frame-1398-living-only.png',M+COL+G,y,COL,277)
p('FIRST RECOVERY, LIVING ONLY - the defect survived hiding the kitchen. The new full-coverage result is shown in fixed view 03.',M+COL+G,right,COL,'small')

y=top('Geometric frame and floor evidence','One shared living/bedroom similarity removes the artificial local tilt; residual reconstruction error is still possible.')
left=img(RUN/'analysis/allviews-elevation-and-floorplan.png',M,y,CW,333)
y=left
y=p(f'All {V["frame"]["camera_count"]} original poses checked. Maximum source-projection invariance residual: {V["frame"]["projection_invariance_max_pixels"]:.3g} pixels. Quaternion/matrix residual: {V["frame"]["camera_quaternion_matrix_error"]:.3g}. Both embedded texture byte streams match their native source textures.',M,y,CW,'small')
p('Plot coordinates are approximate metres from learned depth and the existing component alignment. Flat display axes and a low fitted inlier residual do not establish surveyed dimensions or a globally perfect floor.',M,y,CW,'small')

y=top('Full native selected: delivery caps removed','The user chose the full native model. The smaller simplification experiments remain archived and are not the primary delivery.')
rows=[['Representation','Triangles / bytes','Surface and delivery interpretation'],['PRIMARY - full native',f'{V["mesh"]["triangles"]:,} / {mb(V["mesh"]["bytes"])}','Every native position, normal, UV and triangle index retained exactly. No post-extraction simplification, ownership crop or geometry height cut.'],['Archived small review',f'{FAST["mesh"]["triangles"]:,} / {mb(FAST["mesh"]["bytes"])}','Met its old size/count targets but failed the sampled 2 mm error gate. Not selected for primary delivery.'],['Current policy','No delivery size or triangle cap','Explicit user choice: Full native; bigger size is acceptable; remove limitations. The native extraction is the geometry baseline.'],['Native preservation check','Nine identical cameras / fixed masks',f'Native array identity: PASS. Worst newly empty fraction {V["compaction"]["maximum_new_hole_fraction"]*100:.4f}%. The delivered GLB and offline decoded payload match the native reference SHA-256.']]
y=table(rows,M,y,[157,195,CW-352])
y=p(html.escape(MANUAL['compaction_finding']),M,y,CW)
y=p('Independent surface check: deterministic area-weighted samples in both directions, exact nearest triangle search for each sample. These are approximate scene metres, not survey units. A finite sample pass is not a certified global Hausdorff bound; a sample above 2 mm is sufficient to reject that sampled gate.',M,y,CW,'small')
p('An early sampler mistakenly reused one mutable vector for every point. That report is quarantined as invalid. The corrected sampler creates independent vectors; its distributions, outliers and scripts are attached. No invalid result is used as acceptance evidence.',M,y,CW,'small')

y=top('Alternative extraction pilot: tested and archived','Argon\'s optional merge 0.65 / grid 640 recipe was checked on the same corrected kitchen checkpoint; it is not the selected full native output.')
alt=read(RUN/'analysis/alternative-kitchen-deviation.json');ablation=read(RUN/'analysis/verification-alternative-kitchen-raw/depth-and-hole-checks.json');altviews=next(r for r in ablation['results'] if r['kind']=='compact')['views']
left=p('The alternative kitchen extraction produced 3,714,448 triangles, versus 5,406,238 for the selected 0.5 / default-grid baseline. It reduced count by about 31% while retaining the same training checkpoint and source cameras.',M,y,COL)
left=p(f'Its nine-view ablation against the selected native baseline reached {max(r["new_hole_pixel_fraction"] for r in altviews)*100:.4f}% newly empty pixels. This passes the 0.5% regression bound; it does not establish literally zero new floor/wall holes.',M,left,COL)
left=p('A 1 mm-estimator simplification requested 950k kitchen triangles but stopped at 1,008,499. The independent check found three native-to-simplified samples above 2 mm (maximum 2.110 mm); the reverse maximum was 1.658 mm. It did not pass the strict sampled gate.',M,left,COL)
left=p('The user then selected full native geometry and removed the delivery caps. The coarser pilot and its measurements remain archived; no additional living-room alternative extraction was launched.',M,left,COL,'small')
right=img(RUN/'analysis/verification-alternative-kitchen-raw/after-02.png',M+COL+G,y,COL,312)
p('Actual browser/source comparison for the alternate kitchen. The final primary uses the finer 0.5 native extraction instead.',M+COL+G,right,COL,'small')

y=top('Depth layers and native preservation','Red = background inside the diagnostic mask. Orange = two front-facing layers 3-40 cm apart. Flags require review.')
rawrows=next(r for r in DEPTH['results'] if r['kind']=='raw')['views'];smallrows=next(r for r in DEPTH['results'] if r['kind']=='compact')['views']
rows=[['View','Raw background %','Delivered background %','Newly empty after delivery %','3-40 cm double layers %']]
for a,b in zip(rawrows,smallrows):rows.append([a['name'].replace('frame_000',''),f'{a["hole_pixel_fraction"]*100:.3f}',f'{b["hole_pixel_fraction"]*100:.3f}',f'{b["new_hole_pixel_fraction"]*100:.4f}',f'{b["double_front_layer_fraction"]*100:.2f}'])
y=table(rows,M,y,[185,130,130,172,CW-617]);p('Interior masks cover the indoor source photo; windows and genuinely unseen regions need manual interpretation. The dollhouse mask is a coarse convex floor envelope, fixed from the raw mesh. It includes spaces that may be unobserved, so its absolute hole percentage is not a room-completeness score.',M,y,CW,'small')

y=top('Why a low hole score is not sufficient','Foreground ghost sheets can cover background rays while representing the wrong physical surface.')
yy=img(RUN/f'analysis/verification-{STAGE}/compact-depth-3.png',M,y,COL,325);p('DOORWAY - depth-layer diagnostic at fixed view 03.',M,yy,COL,'small')
yy=img(RUN/f'analysis/verification-{STAGE}/compact-depth-overview.png',M+COL+G,y,COL,325);p('DOLLHOUSE - the fixed floor-envelope mask used for raw/compact regression.',M+COL+G,yy,COL,'small')
p('Two nearby legitimate surfaces can trigger orange; it does not by itself prove self-intersection. A zero background ray can still hit a wrong sheet. The source-photo comparison, depth diagnostic and raw/compact invariant are complementary checks.',M,97,CW)

y=top('Actual browser controls and offline delivery','The final review asset is loaded in Chrome with the hardware RTX 5080 renderer; logic-only checks are not substituted.')
perf=next(r['evidence'] for r in CONTROLS['checks'] if r['name'].startswith('60 FPS'));orbit=next(r['evidence'] for r in CONTROLS['checks'] if r['name'].startswith('Full model orbit'))
left=p(f'<b>{sum(r["pass"] for r in CONTROLS["checks"])} / {len(CONTROLS["checks"])} checks passed.</b> Walk: {perf["averageFps"]:.1f} FPS, 95th-percentile frame {perf["p95Ms"]:.2f} ms. Orbit: {orbit["averageFps"]:.1f} FPS, P95 {orbit["p95Ms"]:.2f} ms.',M,y,COL)
left=p('Checked WASD directions, Q/E and Space/C height, Shift speed, both key-overlap release orders, yaw/pitch without roll, wheel, top view, 90-degree rotation, reset, all eight recorded presets and source comparison.',M,left,COL)
left=p(f'The actual {INTEGRITY["offline_html_bytes"]/1e6:.1f} MB standalone file loaded from disk with zero HTTP requests. The model is embedded in {INTEGRITY["offline_chunks"]} bounded pieces; decoding their combined bytes reproduces the native GLB hash exactly. Source photos are embedded. Key-release state was captured before reset/cleanup could hide a stuck key.',M,left,COL)
left=p('Performance is measured for this desktop, viewport and session. It is not a guarantee for other GPUs, mobile browsers or a larger native mesh.',M,left,COL,'small')
right=img(RUN/f'analysis/verification-{STAGE}/fixed-standalone.png',M+COL+G,y,COL,307)
p(html.escape(perf['renderer']['renderer']),M+COL+G,right,COL,'tiny')

y=top('Remaining issues, recommendation and architect questions','A bounded next experiment should resolve a specific uncertainty, with the current baselines retained.')
left=heading('Issues and struggles',M,y)
for text in MANUAL['remaining_issues']:left=p('- '+html.escape(text),M,left,COL)
right=heading('Recommended next direction',M+COL+G,y)
for text in MANUAL['recommendations']:right=p('- '+html.escape(text),M+COL+G,right,COL)
y=min(left,right)-7
y=heading('Questions for Gemini Argon',M,y,CW)
for text in MANUAL['architect_questions']:y=p('- '+html.escape(text),M,y,CW,'small')

y=top('Evidence and reproducibility','The attached pack contains unchanged screenshots and machine-readable records, with source paths and SHA-256 hashes.')
y=p('Primary review model SHA-256:<br/><font face="Mono">'+V['mesh']['sha256']+'</font>',M,y,CW,'small')
y=p('Native reference SHA-256:<br/><font face="Mono">'+RAW['mesh']['sha256']+'</font>',M,y,CW,'small')
y=p('Included: architectural mandate; explicit full-native delivery decision; exclusion and depth-alignment audit; component transforms; seed/projection records; exact training/meshing commands; all eight before/after WebGL screenshots and overview; layer maps; archived compaction samples; native GLB and offline byte-identity checks; corrected two-calibration COLMAP readback; actual control/offline results; updated implementation sources.',M,y,CW)
y=p('The original three-model architecture PDF and historical Nikon/Samsung image/provenance snapshots are included for context. Large training checkpoints and native GLBs stay in the local scan folder; their verified absolute paths and hashes identify them without duplicating gigabytes into the pack.',M,y,CW)
y=p('Reproduction entry points: scripts 20/21 prepare, seed, train and mesh component datasets; 26 runs the all-usable-view living correction; 22 stages component meshes; 25 verifies a candidate and prevents promotion without its acceptance gates. Viewer compression, rendering and input checks are preserved under viewer-src.',M,y,CW,'small')
p('This report records what was observed. It does not turn learned depth into surveyed accuracy, training-image agreement into independent validation, or failed surface/error gates into a complete release.',M,y,CW,'small')
c.save();WORK.mkdir(parents=True,exist_ok=True);(WORK/'layout_checks.json').write_text(json.dumps({'pages':page,'titles':titles,'checks':layout},indent=2),encoding='utf-8')
print(json.dumps({'pdf':str(PDF),'pages':page,'bytes':PDF.stat().st_size,'sha256':sha(PDF)}))
