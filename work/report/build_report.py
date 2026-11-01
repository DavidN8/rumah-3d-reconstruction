from pathlib import Path
import json, math, hashlib, shutil, zipfile, html
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph, Table, TableStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import ImageReader
from PIL import Image

BASE=Path(__file__).parent
PACK=BASE/'reference_pack'
OUT=BASE.parents[1]/'outputs'
OUT.mkdir(exist_ok=True)
PDF=OUT/'Gemini_Argon_Reconstruction_Architecture_Report_2026-10-27.pdf'
MAN=json.loads((PACK/'manifest.json').read_text(encoding='utf-8'))
W,H=landscape(A4)
M=38
CW=W-2*M
G=22
COL=(CW-G)/2
INK=colors.HexColor('#172B3A')
MUTED=colors.HexColor('#536B79')
TEAL=colors.HexColor('#147D87')
LIGHT=colors.HexColor('#EDF4F6')
LINE=colors.HexColor('#CCDAE0')
AMBER=colors.HexColor('#A75C12')
RED=colors.HexColor('#A53838')
GREEN=colors.HexColor('#267054')
for name,file in [('Body','calibri.ttf'),('Bold','calibrib.ttf'),('Mono','consola.ttf')]:
    pdfmetrics.registerFont(TTFont(name,str(Path('C:/Windows/Fonts')/file)))
pdfmetrics.registerFontFamily('Body',normal='Body',bold='Bold',italic='Body',boldItalic='Bold')
ST={
 'body':ParagraphStyle('body',fontName='Body',fontSize=11.1,leading=14.7,textColor=INK,spaceAfter=7),
 'small':ParagraphStyle('small',fontName='Body',fontSize=9.3,leading=12.2,textColor=MUTED,spaceAfter=5),
 'tiny':ParagraphStyle('tiny',fontName='Body',fontSize=8.2,leading=10.4,textColor=MUTED,spaceAfter=4),
 'h2':ParagraphStyle('h2',fontName='Bold',fontSize=15.4,leading=18.6,textColor=TEAL,spaceAfter=8),
 'h3':ParagraphStyle('h3',fontName='Bold',fontSize=12,leading=15.6,textColor=INK,spaceAfter=6),
 'mono':ParagraphStyle('mono',fontName='Mono',fontSize=8.1,leading=10.6,textColor=INK,wordWrap='CJK',spaceAfter=4),
 'table':ParagraphStyle('table',fontName='Body',fontSize=9.5,leading=12.2,textColor=INK),
 'tablehead':ParagraphStyle('tablehead',fontName='Bold',fontSize=9.5,leading=12.2,textColor=colors.white),
 'cover':ParagraphStyle('cover',fontName='Bold',fontSize=29,leading=32,textColor=INK),
}
c=canvas.Canvas(str(PDF),pagesize=(W,H),pageCompression=1)
c.setTitle('Reconstruction architecture handoff - iPhone, Codex Nikon Z8, Samsung')
c.setAuthor('Codex - prepared for Gemini Argon (Architect)')
c.setSubject('Evidence, failures, fixes, comparison, unresolved risks and recommended next steps')
page=0
titles=[]
checks=[]

def p(text,x,y,w=CW,style='body',gap=None):
    para=Paragraph(text,ST[style]); aw,ah=para.wrap(w,H)
    if y-ah < 38:
        raise RuntimeError(f'Page {page} overflow: {text[:90]!r}, bottom={y-ah:.1f}')
    para.drawOn(c,x,y-ah)
    checks.append({'page':page,'kind':'text','bottom':round(y-ah,2),'sample':text[:60]})
    return y-ah-(ST[style].spaceAfter if gap is None else gap)

def bullet(text,x,y,w=COL):
    c.setFillColor(TEAL);c.circle(x+3,y-6,2,fill=1,stroke=0)
    return p(text,x+13,y,w-13)

def section(title,text,x,y,w=COL):
    y=p(title,x,y,w,'h2');return p(text,x,y,w)

def top(kicker,title,sub=None):
    global page
    if page: c.showPage()
    page+=1;titles.append(title)
    c.setFillColor(colors.white);c.rect(0,0,W,H,fill=1,stroke=0)
    c.setFillColor(TEAL);c.rect(0,H-8,W,8,fill=1,stroke=0)
    c.setFillColor(MUTED);c.setFont('Bold',8.5);c.drawString(M,H-29,kicker.upper())
    y=p(title,M,H-40,CW,'cover' if page==1 else 'h2',gap=8)
    if sub:y=p(sub,M,y,CW,'small',gap=11)
    c.setStrokeColor(LINE);c.line(M,31,W-M,31)
    c.setFillColor(MUTED);c.setFont('Body',8)
    c.drawString(M,19,'GEMINI ARGON / ARCHITECT  |  27 OCT 2026  |  Evidence-based handoff')
    c.drawRightString(W-M,19,f'{page:02d}')
    c.bookmarkPage(f'page{page}');c.addOutlineEntry(title,f'page{page}',0,False)
    return y

def img(fid,x,y,w,maxh=None):
    a=next(a for a in MAN['images'] if a['id']==fid)
    path=PACK/a['file']; iw,ih=a['dimensions'];rh=w*ih/iw
    if maxh is not None and rh>maxh:
        rh=maxh;rw=rh*iw/ih
    else:rw=w
    xx=x+(w-rw)/2
    if y-rh<38:raise RuntimeError(f'Image overflow {page} {fid}')
    c.drawImage(ImageReader(str(path)),xx,y-rh,width=rw,height=rh,mask='auto')
    checks.append({'page':page,'kind':'image','id':fid,'bottom':round(y-rh,2)})
    return y-rh-7

def crop_image(fid,box,x,y,w,h):
    # PDF clipping only: the image in the reference pack remains byte-identical.
    a=next(a for a in MAN['images'] if a['id']==fid)
    path=PACK/a['file'];iw,ih=a['dimensions'];l,t,r,b=box
    scale=min(w/(r-l),h/(b-t));dw=(r-l)*scale;dh=(b-t)*scale
    xx=x+(w-dw)/2; yy=y-dh
    c.saveState();q=c.beginPath();q.rect(xx,yy,dw,dh);c.clipPath(q,stroke=0)
    c.drawImage(ImageReader(str(path)),xx-l*scale,yy-(ih-b)*scale,width=iw*scale,height=ih*scale,mask='auto')
    c.restoreState()
    return y-dh-7

def caption(text,x,y,w=COL):return p(text,x,y,w,'small',gap=9)

def table(rows,x,y,widths,header=True,font='table'):
    ds=[]
    for i,row in enumerate(rows):
        ds.append([Paragraph(str(v),ST['tablehead' if header and i==0 else font]) for v in row])
    t=Table(ds,colWidths=widths,hAlign='LEFT')
    cmds=[('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),8),('RIGHTPADDING',(0,0),(-1,-1),8),('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7),('LINEBELOW',(0,0),(-1,-1),.4,LINE)]
    if header:cmds.append(('BACKGROUND',(0,0),(-1,0),TEAL))
    for i in range(1 if header else 0,len(rows)):
        if i%2:cmds.append(('BACKGROUND',(0,i),(-1,i),LIGHT))
    t.setStyle(TableStyle(cmds));aw,ah=t.wrap(sum(widths),H)
    if y-ah<38:raise RuntimeError(f'Table overflow page {page}, bottom {y-ah:.1f}')
    t.drawOn(c,x,y-ah);checks.append({'page':page,'kind':'table','bottom':round(y-ah,2)})
    return y-ah-12

def callout(title,text,x,y,w=CW,color=TEAL):
    tt=Paragraph(f'<b>{title}</b><br/>{text}',ST['body']); aw,ah=tt.wrap(w-24,H)
    c.setFillColor(LIGHT);c.roundRect(x,y-ah-20,w,ah+20,5,fill=1,stroke=0)
    c.setFillColor(color);c.rect(x,y-ah-20,4,ah+20,fill=1,stroke=0)
    tt.drawOn(c,x+13,y-ah-10)
    if y-ah-20<38:raise RuntimeError(f'Callout overflow page {page}')
    return y-ah-33

def model(mid):return next(m for m in MAN['models'] if m['id']==mid)
def record(sid):return next(s for s in MAN['records'] if s['id']==sid)

# 01 - Executive briefing.
y=top('Decision brief / prepared by Codex','Reconstruction quality: what failed,<br/>what is fixed, what needs an architect',
      'For Gemini Argon (Architect) | iPhone wide + Codex Nikon Z8 + accepted Samsung bedroom/bathroom')
y=callout('Current conclusion','The extra iPhone holes were largely caused by my export cleanup. I removed 125,496 useful source triangles after the compact model already met the size budget. Those cuts are now disabled. The restored export still has warped and incomplete source geometry, so the visual-quality gate remains PARTIAL. [S01, S02, S07]',M,y)
ly=y
ly=section('What I need from Argon','Choose a recovery route that first preserves observed surfaces, then improves geometry and alignment, and only then reduces delivery cost. Please review the proposed validation gates before another long training run.',M,ly)
ly=p('<b>Current iPhone:</b> 1,082,185 triangles; 60,834,340 bytes (60.8 MB); 501 cameras in the corrected frame. Surface-preserving export is reproducible. Navigation and offline checks pass; geometry acceptance does not. [S01-S06]',M,ly,COL)
ly=p('<b>Comparison rule:</b> Nikon means the historical <b>Codex native-camera-kitchen-034</b> test: 24,000 steps, 84 source frames, 576,595 triangles. Other agents\' later Nikon variants are excluded. Samsung means the accepted cleaned bedroom/bathroom release. [S14-S24]',M,ly,COL)
ry=img('F02',M+COL+G,y,COL,maxh=255)
caption('Current iPhone browser view, after restoring all compact source faces. Remaining holes and overlapping surfaces are visible. This is not a completed quality repair. [F02]',M+COL+G,ry)
p('<b>Quick reading route:</b> pp. 2-4 identify and compare the models; pp. 6-7 show the cleanup failure; pp. 8-11 show all current source comparisons; pp. 14-15 explain alignment/input uncertainty; pp. 20-23 contain gates, lessons, the plan and questions; p. 25 records technical settings.',M,68,CW,'small')

# 02 - Scope and identity.
y=top('01 / Provenance','The exact three models in this report','Version identity is established from local binaries, manifests, status records and Codex chat history; not from a generic model selector.')
rows=[['Model / version','Selected artifact and scope','Verified status / important limit'],
 ['iPhone wide<br/><b>20261027_IPHONE_WIDE</b>','Current exports/iphone-full-room.glb<br/>Three temporal training zones; apartment footprint.','<b>PARTIAL</b> visual quality.<br/>1,082,185 triangles / 60.8 MB. Zero compact faces removed by current export.'],
 ['Nikon Z8<br/><b>Codex native-camera-kitchen-034</b>','exports-native-camera-kitchen-034/native-camera-kitchen.glb<br/>Display wrapper: native-camera-kitchen-preview.glb.','<b>Quality rejected</b> historical local test.<br/>84 consecutive source frames; not a full-room reconstruction.'],
 ['Samsung bedroom + bathroom<br/><b>Accepted room-models release</b>','20261019_095800/high-quality/exports/cleaned/<br/>bedroom-bathroom-cleaned.glb<br/>Roofless sibling is used for the overview.','Accepted visual reference, with known gaps.<br/>9,080,740 triangles full; 8,569,710 roofless. Physical scale uncalibrated.']]
y=table(rows,M,y,[168,310,CW-478])
left=y
left=section('Nikon selection, explicitly','The archived Codex chat <b>Run Graphify on RuangKamar</b> records the 22k-to-24k continuation and rejection of the 034 preview. The separate chat <b>Fix kitchen reconstruction preview</b> preserved the same geometry while repairing packaging. Raw and display hashes match the Oct 24 handoff. [S19-S24; provenance JSON]',M,left)
right=y
right=section('Scope of this handoff','This report audits existing evidence and creates a PDF/reference pack. No Samsung or Nikon asset was modified, retrained or published. The iPhone fixes described here were done earlier in this chat; proposals for future work are clearly labelled.',M+COL+G,right)
right=p('<b>Excluded:</b> exports-broader and Nikon 041/042/043/044 or guided variants. Their reports are not used as the Nikon outcome in this comparison. The selected Codex model is not claimed to be the best historical checkpoint.',M+COL+G,right,COL)

# 03 - Three overview plates.
y=top('02 / Visual comparison','Three outcomes, shown with their true scope','Overview images are illustrative. Cameras, framing, model scale, cut height and reconstruction scope differ; this is not a controlled hardware benchmark.')
gap=15;tw=(CW-2*gap)/3
cards=[('F02','iPhone - current preserve export','1.08M triangles / 60.8 MB','Broader apartment coverage, but holes, folded walls, ghost surfaces and softened details remain.'),
 ('F04','Nikon Z8 - Codex 034','576,595 triangles / 42.0 MB','Only the local cooker/counter section. Objects are recognizable, but the saved model was explicitly rejected for severe holes and fragmentation.'),
 ('F03','Samsung - accepted dollhouse','8.57M triangles / 419.8 MB','More coherent bedroom surfaces in this view. This release preserves far more geometry and still contains bathroom/occlusion gaps.')]
for k,(fid,title,stats,desc) in enumerate(cards):
    x=M+k*(tw+gap);z=p(title,x,y,tw,'h3');z=img(fid,x,z,tw,maxh=198);z=p(stats,x,z,tw,'h3');p(desc,x,z,tw)
y2=y-310
p('<b>What this comparison can establish:</b> Samsung supplies a useful conservative processing reference. Codex Nikon is evidence of a local reconstruction failure, despite higher source resolution. iPhone demonstrates an additional, proven cleanup regression. These outcomes cannot be explained by camera brand alone.',M,y2,CW)
p('References: F02 current actual WebGL view; F04 user-provided screenshot of the Codex 24k kitchen preview; F03 saved release browser screenshot. Full-resolution originals are included in the reference pack.',M,y2-64,CW,'small')

# 04 - Quantitative comparison.
y=top('03 / Capture and pipeline','What differs between the three runs','Source-report values are labelled as records, not newly repeated experiments. MB uses decimal bytes / 1,000,000.')
rows=[['Property','iPhone wide - current','Nikon Z8 - Codex 034','Samsung - accepted release'],
 ['Source recording','1080 x 1920 portrait; 4,705 decoded frames, about 156.9 s. [S26]','5,613 developed RAW working frames, 8256 x 4644; 25 fps timeline. Originals preserved. [S19]','2160 x 3840 source; 7,964 frames; 132.91 s, about 59.92 fps. [S17]'],
 ['What was reconstructed','634 selected images; 501 registered. Initially two SfM components, 176 + 325. Three trained zones. [S12]','84 frames, indices 2884-2967, about 3.3 s; 336 overlapping native-pixel tiles. Not all video frames. [S19, S23]','410 bedroom views + 94 bathroom views. Door/light transition 106.55-110.70 s excluded. [S17]'],
 ['Training record','40k steps / 2.5M splat cap per zone. Existing checkpoints reused; no retraining during fixes. [S12]','24k steps, 600k cap; last 2k continuation saved. Camera optimization disabled. [S19, S21]','50k per room; bedroom depth supervision added after 30k; roughly 3M / 2M splat caps. [S17, S18]'],
 ['Delivery geometry','1,082,185 triangles; 60.8 MB.<br/>Original source export 11,641,867 triangles / 539.4 MB.','576,595 triangles; raw 41,979,020 bytes; 1 embedded 8K texture.','Cleaned full 9,080,740 / 425.8 MB.<br/>Roofless 8,569,710 / 419.8 MB.'],
 ['Cleanup / export policy','Compact re-extraction, then preserve all compact faces; roof-only display cutaway.','Local mesh from sparse initialization and depth/normal guidance; porous rejected surface.','Inspected local removals; retained positions, normals, UVs and two 8K PNGs preserved. No global decimation/remesh.'],
 ['Scale / acceptance','Approximate metric frame; depth-backed seam estimate, not surveyed. Visual gate PARTIAL.','Uncalibrated scene units; incomplete local test, quality rejected.','Approximate doorway similarity; uncalibrated physical scale. Accepted visual release with limits.']]
y=table(rows,M,y,[112,(CW-112)/3,(CW-112)/3,(CW-112)/3])
p('Do not compare logged PSNR/SSIM across these runs as a mesh-quality ranking: they use different views, representations and evaluation conditions. An 8K texture is not evidence of complete or dimensionally accurate polygons.',M,y,CW,'small')

# 05 - Work actually completed.
y=top('04 / Work performed','What I changed in the iPhone reconstruction','Completed work is separated here from the recovery experiments proposed later. Source videos and trained checkpoints were preserved.')
left=y
left=section('Frame, scale and registration','Backed up the prior delivery and source scripts. Estimated camera world-up from all 501 poses; fitted floor planes; baked proper rotations, scale and translations into mesh positions/normals. Applied the same per-zone transformations to corrected cameras. Removed redundant viewer conversion. [S03, S04, S28]',M,left)
left=p('Recomputed a 76-frame subset with metric depth output, diagnosed unreliable joins, and used floor/camera-height constraints plus 18 unique depth-backed matches to estimate the kitchen seam. Marked precise registration unverified. [S01, S09-S11, S27]',M,left,COL)
left=section('Delivery and navigation','Re-extracted compact zone meshes and rebuilt one merged GLB. Added direct Three.js walk/orbit navigation, level movement, gentle wheel steps, top/reset/rotate controls, eight recorded source comparisons, and a self-contained offline HTML preview.',M,left)
right=y
right=section('My cleanup error and correction','I introduced broad camera-ownership/height cuts after compaction. These removed valid surfaces. After the user flagged the missing mesh, I rendered controlled stage comparisons, identified the deletion step, preserved the bad delivery for diagnosis, and changed the default to preserve every compact face. [S07, S08]',M+COL+G,right)
right=p('I also disabled the display floor clip and the inferred doorway replacement. The current export reports zero removed compact faces in all three zones. The roof cutaway is a viewing feature; the complete model remains available. [S02]',M+COL+G,right,COL)
right=section('What I have not done','I have not regenerated the original seed cloud, retrained the three checkpoints with the corrected depth preprocessing, established a robust independent full-scene bridge, surveyed dimensions, or completed a faithful surface repair. The model remains visually incomplete.',M+COL+G,right)

# 06 - User failure and accountability.
y=top('05 / Root cause','Why the user saw large missing areas','The current complaint exposed a real regression in my work. It is not defensibly explained as an iPhone capture limitation.')
left=img('F01',M,y,COL,maxh=258)
left=caption('User screenshot of the defective delivery. The black background exposes absent geometry. Its viewpoint is different from the controlled comparison on the right. [F01]',M,left)
left=p('<b>My mistake:</b> I treated nearest-camera/field-of-view support as evidence that a triangle belonged to a room. A point can lie inside a camera frustum and still be hidden behind a wall. The heuristic discarded useful walls and floors. Triangle count and file size checks did not detect this. [S07; implementation snapshot]',M,left,COL)
right=img('F06',M+COL+G,y,COL,maxh=260)
right=caption('Controlled comparison: compact source before my cuts (left) versus the previous delivery (right), using the same camera, corrected transforms and roof cut. The bedroom loses substantial surfaces after cleanup. [F06, S08]',M+COL+G,right)
right=p('<b>Arithmetic:</b> 1,082,185 compact triangles - 125,496 source triangles deleted + 1,152 inferred patch triangles = 957,841 previously delivered triangles. The cleanup was unnecessary for the agreed delivery budget. [S07]',M+COL+G,right,COL)
right=p('<b>Now:</b> retain all 1,082,185 compact triangles, with the broad cuts and patch disabled. Restoring faces reverses this regression; it does not cure the underlying warped/porous reconstruction.',M+COL+G,right,COL)

# 07 - Controlled ablation.
y=top('06 / Controlled diagnosis','Where geometry was lost in the pipeline','All four renders use the same camera, per-zone transforms and roof cut. Display effects and actual mesh deletion are separated. [S07, S08]')
iw=(CW-18)/2; ih=157
for k,(fid,title,txt) in enumerate([
 ('F07','A - Original source, 11.64M','Most complete of these stages; already warped/porous.'),
 ('F08','B - Compact, 1.082M','Re-extraction loses some detail and creates a smaller floor gap.'),
 ('F09','C - Previous export, 0.958M','Large additional bedroom losses after automatic cuts.'),
 ('F10','D - Same export + old floor clip','Similar here: floor clipping is not the main cause in this view.')]):
    x=M+(k%2)*(iw+18); z=y-(k//2)*210
    z=p(title,x,z,iw,'h3');z=crop_image(fid,(315,190,1220,850),x,z,iw,ih);caption(txt,x,z,iw)
p('All four images use the same PDF crop for readability; full frames are attached. This comparison supports cleanup as the largest observed regression in this tested view, not a measured percentage of all missing area. Original reconstruction and remeshing errors remain separate contributors.',M,64,CW,'small')

# 08-11 - All eight current comparisons, two per page.
viewmeta=[
 ('Kitchen / counter','999','Shelves and broad surfaces are recognizable, but small containers and sink-side surfaces are soft, fused or missing.','F15'),
 ('Kitchen / appliances','903','Inspect appliance edges, countertop continuity and surface thickness. Recognizable appearance does not establish faithful object geometry.','F16'),
 ('Doorway / transition','1398','Door and wall surfaces fold/overlap near the seam. The small depth residual reported later does not eliminate this visible defect.','F17'),
 ('Living area','1612','Review furniture and wall continuity beyond the best-looking central floor. Source details should remain the acceptance reference.','F18'),
 ('Living / windows','2402','Large surfaces and furnishings remain softened. Reflections and moving content require separate diagnosis, rather than blanket deletion.','F19'),
 ('Corridor / bed','3606','The source shows a coherent ceiling and bedroom opening; the mesh still shows torn/ghosted surfaces. Restoration has not resolved these.','F20'),
 ('Bedroom / desk','4297','Evaluate the desk area, wall continuity and ghost geometry. Zone labels are temporal partitions, not a guarantee of semantic room ownership.','F21'),
 ('Bedroom entrance','4400','Check whether the room entrance and interior surfaces agree across views. This view is part of an unfinished quality gate.','F22')]
for j in range(4):
    y=top(f'07 / Current iPhone evidence {j+1} of 4',f'Recorded-view checks: {viewmeta[2*j][0]} + {viewmeta[2*j+1][0]}','Actual browser render on the left of each image, original source photograph on the right. Same corrected camera pose; full image originals are attached.')
    for k in range(2):
        label,frame,txt,fid=viewmeta[2*j+k];x=M+k*(COL+G)
        z=p(f'{2*j+k+1:02d} / {label} - frame {frame}',x,y,COL,'h3');z=img(fid,x,z,COL,maxh=276)
        z=p(txt,x,z,COL);p(f'Image {fid}. Browser capture from current 1,082,185-triangle export. These eight views expose failures; they are not a complete-room coverage audit. [S01, S04]',x,z,COL,'small')

# 12 - Coordinate contract and technical architecture.
y=top('08 / Coordinate contract','One transform for geometry and its cameras','Correcting a display frame fixes orientation and numerical consistency. It does not fix source geometry or validate room dimensions.')
left=y
left=section('Observed frame, not an assumption','Averaging camera local-up transformed to world coordinates gives approximately [0.0047, 0.0181, 0.9998]: the original world was already close to +Z-up. Camera +Y-down conventions alone do not identify world gravity. The original display mapping sent native +Z toward glTF -Y. [S03]',M,left)
left=section('Current export mapping','For each zone, bake p\' = s R p + t into positions; rotate normals by R. Rotations are proper (det R approximately +1). Fitted local floor planes map to Y = 0; XZ centering is shared with camera output. No root orientation wrapper remains. [S02-S04]',M,left)
left=p('Cameras use the same similarity: C\' = s R C + t; world-to-camera rotation Rcv\' = Rcv R transpose. glTF camera orientation also accounts for the CV-to-viewer axis convention. Numerical projection invariance is below 8 x 10^-10 pixels. This verifies the conversion, not camera accuracy. [S04]',M,left,COL)
right=y
right=p('Training coordinates remain frozen',M+COL+G,right,COL,'h2')
right=callout('Preserved input','zones/zone-0, zone-1, zone-2 and their existing checkpoints still use the original training frame. Re-extraction reads those frozen assets.',M+COL+G,right,COL)
right=callout('Explicit correction','analysis/fixed-transforms.json defines per-zone transformations. The merger bakes them into the derivative mesh and creates matching corrected cameras.',M+COL+G,right,COL)
right=callout('Corrected output','colmap-gpu/merged/sparse/0 and corrected/sparse/0 carry a FRAME.json contract. New preprocessing is directed to upright datasets to prevent mixing old checkpoints with new poses.',M+COL+G,right,COL)
right=p('<b>Architectural concern:</b> local floor leveling includes a separate zone-2 adjustment. The export is not one unchanged rigid transform of the entire original living/bedroom component. Cross-zone continuity still requires visual and geometric validation.',M+COL+G,right,COL)

# 13 - Floor and trajectory evidence.
y=top('09 / Frame verification','Floor alignment and camera paths','The plot uses the written current GLB and matching 501 camera positions, not only a transform table. [S04]')
left=img('F11',M,y,CW*.64,maxh=397)
rx=M+CW*.64+20;rw=CW*.36-20;right=y
right=section('What passes','All three fitted floor datums are numerically at Y = 0. Floor-fit RMS is about 4.4 mm, 9.8 mm and 8.8 mm in the chosen approximate metric frame. The camera/export conversion is internally consistent. [S04]',rx,right,rw)
right=section('What remains uncertain','The kitchen plane near native Z = 0 was initially a countertop, not the tiled floor; the actual floor is lower. That distinction materially affects scale and alignment. [S09]',rx,right,rw)
right=p('Median exported camera heights differ by zone: kitchen 1.412 m, living 1.500 m, bedroom/desk 1.055 m. These are observations in an approximate frame, not proof that every pose should be forced to 1.50 m.',rx,right,rw)
right=p('Detected upper planes near 2.28, 2.42 and 1.96 m may be beams or undersides. They must not be labelled surveyed ceiling heights. [S04]',rx,right,rw)

# 14 - Scale and seam.
y=top('10 / Kitchen alignment','Useful alignment evidence, weak global precision','The current seam is an estimate constrained by learned depth, floors and camera heights. precise_registration_verified remains false. [S01]')
left=img('F12',M,y,COL,maxh=285)
left=caption('18 unique LoFTR matches, largely on one switch-plate patch, between source frames 1386 and 1390. A planar, localized feature set poorly constrains a global room join. [F12]',M,left)
left=p('Sparse 3D track matching found no reliable common associated tracks. The optical-flow triangulation attempt failed its checks. Those attempts were rejected, not silently treated as independent confirmation.',M,left,COL)
right=y
rows=[['Current estimate','Value / interpretation'],
 ['Living scale','4.00448 m per legacy training unit; anchored to an assumed 1.50 m median living camera height.'],
 ['Kitchen correction','0.463399 relative to the already joined legacy training frame; yaw correction about 3.53 degrees. Not a universal physical enlargement factor.'],
 ['Depth-point residual','Median 0.00763 m; P90 0.01798 m, after the constrained fit. Internal fit residual, not an independent accuracy guarantee.'],
 ['Seam camera heights','Last-four / first-four medians: 1.4936 / 1.4870 m. Last-to-first position step: 0.07865 m. Poses were not forced identical.']]
right=table(rows,M+COL+G,right,[105,COL-105])
right=p('<b>Superseded evidence:</b> bridge-dense-fit.json records the same image pair twice (36 rows). The final solve deduplicates to 18. Its earlier unconstrained transform and smaller residual must not replace the final S01/S03 result. [S11]',M+COL+G,right,COL,'small')
right=p('The original walking-speed scale 0.66055 and a misread units/metre value do not establish physical kitchen shrinkage. Metric depth is also learned, not measured. A known length or independent multi-view bridge is still needed.',M+COL+G,right,COL,'small')

# 15 - Depth preprocessing and root representation issues.
y=top('11 / Unresolved pipeline issue','Depth preparation was corrected; the model was not retrained','A code fix to future input preparation is not a repair to existing checkpoints. This is a key limitation for the next architect.')
left=y
left=section('Two separate depth problems','The original MoGe PNGs were relative, normalized per image. They cannot be interpreted directly as millimetres. I generated a separate 76-frame metric subset using explicit mm output and z-depth convention; it supports the seam estimate without overwriting training inputs. [S10, S27; implementation/14_metric_bridge.py]',M,left)
left=p('In the seed-cloud preparation I found resized depth (about 598 x 1064) paired with full-resolution 1080 x 1920 intrinsics and RGB sampling. The code now scales intrinsics and color sampling consistently to the depth grid, and guards frame selection. Existing seed clouds and trained splats were not regenerated. [implementation/05_seed_cloud.py]',M,left,COL)
left=callout('Implication for diagnosis','The old initialization may have contributed to poor surfaces. The report does not claim how much: that requires a controlled pilot with corrected inputs and the same held-out evaluation.',M,left,COL,color=AMBER)
right=y
right=section('What the remaining artifacts suggest','Folded walls, overlapping sheets, damaged small objects and ghost surfaces appear in current source comparisons. These may involve camera/zone inconsistency, weak initialization, learned-depth error, transient content and splat-to-mesh extraction. The current evidence does not isolate one universal cause.',M+COL+G,right)
right=section('Why more triangles is not enough','The 11.64M source mesh is more complete than the compact one in the ablation, but already contains reconstruction defects. The 8K texture bakes appearance onto whatever surface exists. Increasing iterations or filling holes could preserve or hide an incorrect surface unless geometry is checked independently.',M+COL+G,right)
right=p('<b>Recommended controlled test:</b> one fixed kitchen/doorway subset; corrected depth-grid intrinsics; explicit depth units; verified cameras; frozen random seed/config; a held-out photo set and matched novel viewpoints. Compare original extraction, compact extraction and an error-bounded simplification of the original.',M+COL+G,right,COL)

# 16 - Samsung case.
y=top('12 / Samsung reference','Why the accepted bedroom workflow is the better cleanup precedent','This is a processing comparison, not proof that its camera or every training setting is superior. [S14-S18]')
left=img('F03',M,y,COL,maxh=230)
left=caption('Accepted cleaned roofless release. Bedroom and bathroom remain separate meshes with approximate doorway alignment. [F03]',M,left)
left=p('The full cleanup retained 9,077,606 scanned triangles and added 3,134 separately labelled inferred doorway triangles, for 9,080,740 total. It removed inspected debris/small components and outside-envelope fragments, while preserving retained positions, normals and UVs. [S15]',M,left,COL)
right=y
right=section('Practices worth carrying forward','Separate room training; exclude the moving door/light transition; inspect the weak plain-wall area and add depth guidance; keep original exports; inspect local cleanup regions; isolate inferred geometry in a named node. Original 8K PNG texture bytes were preserved. [S14, S17, S18]',M+COL+G,right)
right=p('The roofless cut uses exact triangle-plane intersections and interpolates UVs/normals. File size also fell by removing unused buffer data. This preserved detail instead of globally re-extracting or decimating the accepted scene. [S14, S15]',M+COL+G,right,COL)
right=section('Limits that remain','This model is not welded or watertight, has mirror/occlusion and wall/floor gaps, and includes an inferred doorway surround. Scale was never physically calibrated. Approximate alignment used 49 stationary landmarks across eight doorway views, not a survey. [S17]',M+COL+G,right)
right=p('Its 425.8 MB full model is roughly seven times the current iPhone file size. A fair future quality comparison must account for the very different geometry budget and capture scope.',M+COL+G,right,COL)

# 17 - Real Samsung source photographs.
y=top('13 / Samsung source evidence','The accepted reference still needs to be judged against photographs','Actual source images are attached. They are historical capture evidence; no new Samsung reconstruction was run for this report.')
iw=(CW-30)/2
z=img('F13',M,y,iw,maxh=333);caption('Bedroom, source f_001130.jpg at 18.834889 s. Original dataset photo; visual benchmark for the room, not a fresh matched render of the cleaned GLB. [F13, S17]',M,z,iw)
z=img('F14',M+iw+30,y,iw,maxh=333);caption('Bathroom, source f_006654.jpg at 111.009489 s, after the excluded light/door transition. Mirrors, glossy tiles and occlusion remain documented limitations in the release. [F14, S14, S17]',M+iw+30,z,iw)

# 18 - Correct Codex Nikon, honest review.
y=top('14 / Nikon Z8, Codex version','Our Nikon result: native-camera-kitchen-034','Selected using the Codex history and matching binary hashes. Another agent\'s later full-room or zone candidates are not substituted here.')
left=img('F04',M,y,COL,maxh=235)
left=caption('User-provided screenshot of the 24k-step Codex kitchen preview. It shows a short counter strip with damaged surfaces and holes, not a complete room. [F04]',M,left)
left=p('This run used 84 of 5,613 source frames, expanded into 336 overlapping native-pixel crops. The full developed 8K image set was preserved, but preserving source images did not mean they were all reconstructed. The broader camera candidate remained split into 29 components. [S19, S23]',M,left,COL)
right=y
right=section('What Codex did historically','Ran local camera/guidance experiments, trained a native-pixel kitchen pilot, resumed from 22k to 24k, meshed it, and packaged source-photo comparison plus a standalone preview. A separate Codex viewer repair preserved exactly the same mesh. [S19-S23; chat provenance]',M+COL+G,right)
right=section('What went wrong','I spent effort refining and packaging a tiny test while full-room camera alignment and obvious surface defects remained unresolved. The user rejected it; the status was changed to quality_rejected. Steps, texture size and frame preservation were poor proxies for a usable result. [S20]',M+COL+G,right)
right=p('Historical automated browser testing was blocked in those chats; Node logic tests did not prove rendering or input behavior. The user screenshot proves that a preview was visible to the user, not that all controls or downloads passed automation. No new Nikon browser pass is claimed here.',M+COL+G,right,COL)

# 19 - Nikon source comparison enlarged.
y=top('15 / Nikon source comparison','The Codex kitchen mesh loses visible source structure','Historical saved source/model renders from the 24k-step run. These images precede the other agent\'s later reconstruction attempts. [F05, S19, S20]')
tw=(CW-30)/3
for k,(stamp,desc) in enumerate([
 ('116.16 s','The source contains coherent bottles, bowls and sink edges. The mesh contains gaps and damaged silhouettes.'),
 ('117.12 s','The white appliance and countertop are softened or fragmented; broad texture resemblance is insufficient.'),
 ('117.92 s','The second appliance and wall regions show holes and smeared surfaces. The local test fails visual acceptance.')]):
    x=M+k*(tw+15);z=p(stamp,x,y,tw,'h3')
    z=crop_image('F05',(k*630,0,(k+1)*630,620),x,z,tw,270)
    z=p('Source (left) / Codex mesh (right)',x,z,tw,'small');p(desc,x,z,tw)
p('These local viewpoints are not a whole-room completeness score. The contact sheet is kept at its original resolution in the reference pack. Nikon source resolution is much higher than the phone captures, but camera recovery, scope selection, initialization and surface extraction still dominate the outcome.',M,102,CW)

# 20 - Verification and limits.
y=top('16 / Verification status','Separate numerical, visual and usability gates','The current iPhone is usable for inspection. It is not accepted as a faithful final reconstruction. [S01-S06]')
rows=[['Gate','Current evidence','Verdict / limit'],
 ['Source protection / identity','49-file original backup manifest; second snapshot preserves my harmful trimmed delivery. Six current comparison binary hashes rechecked for this report.','Preserved. No old scans modified for the report.'],
 ['Export coordinate consistency','501 cameras; proper rotations; fitted floors at Y=0; projection conversion error below 8e-10 pixels; no root frame wrappers.','PASS conversion math. Does not prove recovered camera positions or room geometry.'],
 ['Triangle and byte budget','1,082,185 triangles / 60,834,340 bytes. All three compact source face counts retained. Rebuild SHA-256 identical.','PASS agreed 600k-2M / under 120 MB budget.'],
 ['Browser behavior','33 checks: movement directions, held/released and overlapping keys, drag/orbit/reset, source views, no roll, offline embedded sources, no browser errors.','PASS tested browser automation. Not a physical keyboard/hardware or universal-device guarantee.'],
 ['Performance','Hardware RTX 5080 / Chrome / D3D11; 1440 x 1000; about 240 FPS and 4.3 ms P95 in saved walk/orbit tests.','PASS this setup. No phone, low-memory GPU, network or cold-load benchmark claimed.'],
 ['Seam precision / physical scale','18 localized depth-backed matches; floor/height constraints; sub-2 cm internal P90 residual.','UNVERIFIED globally. Learned depth, assumed scale and local floor adjustments remain.'],
 ['Visual reconstruction quality','Eight actual WebGL/source comparisons; controlled original/compact/trimmed ablation. Visible holes, warped surfaces and ghost geometry remain.','PARTIAL. No full-room quality completion or survey accuracy claimed.']]
y=table(rows,M,y,[133,394,CW-527])
p('The original iPhone report\'s CPU coverage=1.0 and Gaussian image metrics are not accepted as proof of polygon completeness. Gate 2 now returns PARTIAL rather than an unconditional PASS. [S01, S12; implementation/11_gate2_verify.py]',M,y,CW,'small')

# 21 - Struggles / corrected hypotheses.
y=top('17 / Issues, struggles and lessons','What did not work, and what the evidence actually says','Failed experiments are retained as evidence; they are not presented as validated solutions.')
left=y
for title,text in [
 ('A shortcut for zone ownership','Closest camera plus frustum inclusion ignored wall occlusion and deleted valid surfaces. Fixed by disabling broad default cuts; no safe automatic ownership replacement has yet been validated.'),
 ('A misleading scale story','Walking-speed ratios and an initially wrong floor/countertop datum made the original kitchen-scale explanation unreliable. The current correction is an estimate with explicit uncertainty.'),
 ('Weak registration witnesses','Sparse-track and optical-flow bridges failed. Learned matches yielded only one localized planar patch; low fit residual cannot support a high-confidence whole-room claim.'),
 ('Parameter experiments without a quality win','Hybrid extraction settings increased geometry in some zones but produced larger floor gaps and did not repair the bedroom. These candidates were rejected and not promoted.')]:
    left=p(title,M,left,COL,'h3');left=p(text,M,left,COL)
right=y
for title,text in [
 ('Correctness checks missed usefulness','A consistent coordinate transform, a smaller GLB and fast controls all passed while the mesh looked bad. These checks must stay separate from source-based surface acceptance.'),
 ('A real preprocessing fix remains unapplied','The corrected depth-grid intrinsics/color sampling protect future builds. Existing seed clouds and checkpoints still embody the previous preparation; their quality cannot improve merely because the script changed.'),
 ('Temporal zones were overinterpreted','The living/corridor partition includes bedroom content, and the later zone includes the desk area. These labels cannot supply semantic ownership or justify deleting overlap.'),
 ('Scope and cost drift','The Nikon history repeated local experiments without a solved whole-room camera path. A small, falsifiable pilot with a stop condition is preferable to promising that more steps or more splats will finish the scene.')]:
    right=p(title,M+COL+G,right,COL,'h3');right=p(text,M+COL+G,right,COL)

# 22 - Recommended plan.
y=top('18 / Direction and plan','Recommended next steps, in order','These are proposals for Argon\'s review. They have not been executed as part of this reporting task.')
rows=[['Stage','Action and purpose','Evidence required before continuing'],
 ['0 / Freeze the baseline','Keep current preserve-policy export, original source meshes, frozen checkpoints and corrected cameras. Give every candidate an asset hash and transform contract.','One reproducible baseline; preserve all originals. Current bad-trim snapshot remains available for causal comparison.'],
 ['1 / Measure the actual losses','Use the same cameras to compare original 11.64M meshes, current compact meshes and splats. Inspect representative rooms, boundaries and novel views. Record holes, wrong surfaces and silhouette changes separately.','An annotated defect map that says which stage creates each failure. Use depth/visibility tests and source masks; raw occupancy alone is insufficient.'],
 ['2 / Validate alignment','Seek spatially distributed, static correspondences across the doorway; hold some out. Check intrinsics, gravity/floor assumptions and zone-2 continuity. If available, use one or more real known lengths.','Independent photo residuals plus coherent wall/floor structure across views. Keep physical precision unverified if the evidence is insufficient.'],
 ['3 / Run one corrected-input pilot','Regenerate seeds in a separate dataset with depth-grid K/RGB consistency and explicit units. Train a small kitchen/doorway pilot under the same comparison protocol; retain existing checkpoints.','Repeatable visible improvement in geometry, silhouettes and held-out views. Stop if only training image metrics improve.'],
 ['4 / Choose the delivery method','Compare topology/UV-preserving error-bounded simplification of the original against current re-extraction. Evaluate LOD or compression separately if quality exceeds the byte/poly budget.','No material new holes in protected regions. Document surface deviation and small-object loss; bytes/FPS are secondary gates.'],
 ['5 / Release a reviewed candidate','Only remove artifacts with occlusion-aware multi-view evidence or inspected local masks. Label inferred fills separately. Recheck views, exact cameras, offline bundle and target devices.','Visual acceptance, provenance and regression checks pass. Otherwise keep the candidate experimental and report the unresolved defect.']]
y=table(rows,M,y,[98,335,CW-433])
p('Priority recommendation: first isolate camera/initialization defects from mesh-extraction defects; do not begin with global hole filling, forced wall planes, stronger trimming or another blind parameter sweep.',M,y,CW,'small')

# 23 - Questions for architect.
y=top('19 / Questions for Gemini Argon','Decisions I need help making','Please assess the evidence and recommend a bounded next experiment, with explicit success and stop conditions.')
left=y
qs=[
 ('1. Which representation should be the quality baseline?','The original iPhone mesh preserves more coverage but is already warped. Should the next pilot prioritize corrected-camera/depth retraining, or first isolate splat-to-mesh extraction using the existing checkpoint?'),
 ('2. How should overlapping temporal zones be fused?','What occlusion-aware visibility or multi-view consistency test can retain thin walls, floors and furniture while removing duplicate/ghost sheets? The failed nearest-camera/frustum heuristic is documented.'),
 ('3. Is the kitchen join sufficiently constrained?','We have only 18 switch-plate matches plus learned depth and floor/height assumptions. Which distributed correspondences or held-out tests are needed before applying a global similarity?'),
 ('4. Is local floor leveling defensible?','Zone 2 has a separate correction inside a component that originally shared a world frame. Should one gravity transform be enforced, with camera/geometry errors repaired earlier instead?')]
for title,text in qs:left=p(title,M,left,COL,'h3');left=p(text,M,left,COL)
right=y
qs=[
 ('5. What controlled seed/training pilot will isolate the bug?','Please specify a small subset, exact preprocessing invariants, supervision weights to review and evidence that would justify expanding to all zones.'),
 ('6. Can geometry be preserved within the delivery budget?','Should we prefer error-bounded simplification, LOD, mesh compression or texture compression over re-extraction? Which protected features and deviation metrics should be mandatory?'),
 ('7. What is a valid visual completeness gate?','How should we score missing visible surfaces separately from wrong foreground sheets, dynamic objects and unseen areas? Existing PSNR, frustum counts and CPU occupancy gave false confidence.'),
 ('8. What minimum new evidence is truly needed?','Can existing footage and local measurements resolve the uncertainty? If not, identify the exact doorway views or known lengths needed and explain the blocked decision. No capture inadequacy has been established.'),
 ('9. Is a different Codex Nikon checkpoint intended?','This report pins the historical 034 model by hash. If comparing another Codex candidate, identify the exact asset first; do not substitute a later other-agent model or silently rank mismatched scopes.')]
for title,text in qs:right=p(title,M+COL+G,right,COL,'h3');right=p(text,M+COL+G,right,COL)

# 24 - Reproduction and files.
y=top('20 / Reproduction and artifact map','Where to inspect the current result','Paths are local to this Windows machine. The accompanying reference pack allows Argon to review images, records and code without these folders.')
left=y
left=p('<b>Repository root (R):</b>',M,left,COL)
left=p(str(Path(r'C:/Users/bombe/OneDrive/Documents/ChatGPT/Ruang Kamare')).replace('\\','/'),M,left,COL,'mono')
left=p('<b>iPhone scan (IP):</b> R / roomscan-reconstruction/data/20261027_IPHONE_WIDE',M,left,COL)
left=p('Current model: IP / exports/iphone-full-room.glb<br/>Interactive entry: IP / review/open_viewer.bat<br/>Standalone: IP / review/iPhone-Full-Room-preview.html<br/>Current browser: http://127.0.0.1:53251/?mode=orbit&amp;rev=surface-preserved',M,left,COL,'small')
left=p('Core review records: analysis/fixed-verification.json; fixed-transforms.json; fixed-geometry-check.json; fixed-controls-check.json; fixed-rebuild-check.json; missing-mesh-diagnosis/findings.json.',M,left,COL)
left=p('Backups: IP / backups/before-fix-20261027 (original delivery) and IP / backups/before-surface-preservation-20261027 (my harmful trimmed delivery and reports).',M,left,COL)
right=y
right=p('Implementation entry points',M+COL+G,right,COL,'h2')
for name,desc in [
 ('09_merge_export.py','Default preserve policy; bakes transforms/cameras, keeps compact faces. legacy-trim is diagnostic only.'),
 ('16_solve_frame.py / 18_measure_planes.py','Constrained seam/floor solution and plane measurement. Reference the final transform, not the superseded 36-row preliminary fit.'),
 ('19_verify_geometry.py / 11_gate2_verify.py','Written-asset frame checks and source-based quality gate. PARTIAL is a meaningful result.'),
 ('05_seed_cloud.py / 07_train_zone.py','Future corrected-frame preprocessing/training preparation; existing checkpoints have not been rebuilt.'),
 ('room-viewer.js / test-controls.mjs','Viewer behavior and 33 browser checks. Snapshot included; dependencies and models are not included.')]:
    right=p(f'<b>{name}</b><br/>{desc}',M+COL+G,right,COL,'small')
right=p('Do not run old training scripts with corrected cameras and legacy checkpoint data without choosing one frame contract. To reproduce safely, inspect the copied implementation and configuration before launching any processing.',M+COL+G,right,COL)

# 25 - Technical recipe for architectural review.
y=top('21 / Technical settings','Recorded settings: audit these before choosing a pilot','These are effective historical settings and current mesh commands, not a claim that copying any one recipe will solve the geometry problem.')
rows=[['Setting','iPhone checkpoints + current compact mesh','Nikon Z8 - Codex 034','Samsung selected release'],
 ['Training preset / RGB','meshing / quality medium; divisor 1; progressive resolution enabled, full at 0.3. Existing saved configs.','quality high; native-pixel crops, divisor 1; progressive resolution disabled.','quality high; divisor 1; progressive resolution enabled, full at 0.3.'],
 ['Steps / capacity','40k steps and 2.5M cap per zone. Camera optimizer disabled.','24k steps / 600k cap; refinement stopped at 14k. Camera optimizer disabled.','50k per room; cap 3M bedroom / 2M bathroom. Camera optimizer disabled.'],
 ['Depth / normals','Depth weight 0.05; normal weight 0.02. Original seed/data preparation still in checkpoints.','Depth weight 0.05; normal weight 0.02; 1064 x 598 auxiliary guidance.','Bedroom resumed at 30k with depth weight 0.05. Bathroom depth weight 0; selected config normal weight 0.01.'],
 ['Splat size limit','Historical max_world_size = 0.02875 in training units in all three zones. Future script uses measured per-zone physical scale; existing training was not rerun.','max_world_size = Infinity in saved config. Do not infer this alone caused the failed surfaces.','max_world_size = Infinity in saved configs. Successful visual reference shows the clamp is not a universal explanation.'],
 ['Mesh extraction','merge-factor 1.2; iso 0.68; max-grid-res 384; bisection 4; carve-k 3; hole ratio 0; max edges 64; floater minimum 50.','merge-factor 0.5; bisection 4; carve-k 8; hole ratio 0; max edges 8; floater minimum 50. [S19]','Selected mesh recipe: merge-factor 0.5; bisection 4; carve-k 3; hole ratio 0; max edges 64. [S18; command snapshot]'],
 ['Texture / final policy','Three 8192 textures, glb+jpeg90 extraction. Final merger preserves those compact texture bytes and all compact faces.','One 8192 texture. Preview wrapper preserves the raw model payload; geometry was quality rejected.','Two original 8192 PNG textures copied byte-for-byte during cleanup; extra photo texture only for labelled doorway inference.']]
y=table(rows,M,y,[105,240,210,CW-555])
y=p('Evidence: implementation/iphone-zone-0..2-config.json and iphone-zone-0..2-mesh-command.json; S19/S21; Samsung driver/command snapshots and S17/S18. Engine configs may contain Infinity; it denotes an unlimited setting, not missing data.',M,y,CW,'small')
p('Current iPhone work used the RTX 5080 and 16 CPU threads. Earlier Nikon GPU limits/tool restrictions belong to those historical sessions; do not carry their operational policy into a new run without checking the current user instructions. No training was launched to prepare this report.',M,y,CW,'small')

# 26 - Hashes.
y=top('22 / Binary fingerprints','Exact model identity and reproducibility','All six binary hashes below were recalculated while preparing this report. Large model binaries are not duplicated in the reference pack.')
for mid,label in [('IP-current','Current iPhone preserve export'),('IP-before-my-cuts','Previous harmful iPhone trimmed export'),('NI-Codex-034-raw','Codex Nikon 034 - raw mesh'),('NI-Codex-034-display','Codex Nikon 034 - display wrapper'),('SA-accepted-full','Accepted Samsung - full'),('SA-accepted-dollhouse','Accepted Samsung - roofless')]:
    m=model(mid);y=p(f'<b>{label}</b> | {m["triangles"]:,} triangles | {m["bytes"]:,} bytes',M,y,CW,'body',gap=2)
    y=p(m['sha256'],M,y,CW,'mono',gap=9)
p('The current iPhone rebuild also reproduced byte-identical output in the saved verification record. Its standalone HTML is 84,803,417 bytes and contains the current model and eight reference photographs. Hashes prove identity/integrity, not geometric correctness. [S01, S06]',M,y,CW)

# 26-27 - Source register, readable and linked to pack files.
source_desc={
 'S01':'Current combined verdict and final gate results. Authoritative current status.',
 'S02':'Current export accounting: preserve policy, zero compact face removals, baked transforms.',
 'S03':'Final per-zone coordinate/scale transformations; final registration constraints.',
 'S04':'Written-GLB geometry, floor, rotation and camera-projection verification.',
 'S05':'33 browser/control/performance/offline checks and renderer evidence.',
 'S06':'Byte-identical rebuild and all-compact-source-face preservation result.',
 'S07':'Causal cleanup findings and previous-delivery triangle arithmetic.',
 'S08':'Controlled ablation rendering conditions and stages.',
 'S09':'Measured floor/upper-plane evidence; distinguish countertop from floor.',
 'S10':'Fresh depth-based scale estimates by original component.',
 'S11':'PRELIMINARY fit with duplicated pair/36 rows. Superseded by final deduplicated S01/S03.',
 'S12':'PRIOR-AGENT report: original pipeline record and claimed metrics; not a new quality endorsement.',
 'S13':'Original archived walking-speed join; preserved for diagnosis.',
 'S14':'Accepted Samsung release workflow and explicit limitations.',
 'S15':'Samsung cleanup counts, texture hashes, inferred repair and roof-cut details.',
 'S16':'Accepted Samsung release manifest; exact model paths/bytes/hashes.',
 'S17':'Samsung capture, training, alignment and source-view checks.',
 'S18':'Samsung selected depth-supervised bedroom and repaired bathroom settings.',
 'S19':'Codex Oct 24 Nikon failure handoff; scope, settings, hashes and rejection.',
 'S20':'Codex Nikon 034 quality_rejected record; not whole-room complete.',
 'S21':'Codex Nikon 034 effective training configuration.',
 'S22':'Codex Nikon local dataset readiness record.',
 'S23':'Codex Nikon geometry plan, native-pixel crops and auxiliary guidance.',
 'S24':'Later diagnostic of the same Codex 034 binary; image metrics not used to rank models.',
 'S25':'User-pasted prior-agent brief; source context, not a system instruction.',
 'S26':'iPhone decoded/selected frame metadata and dimensions.',
 'S27':'Separate metric-depth subset provenance and explicit output convention.',
 'S28':'Current corrected-camera FRAME.json; frozen checkpoint dataset warning.',
}
for part,ids in enumerate([list(range(1,15)),list(range(15,29))],1):
    y=top(f'23 / Source register {part} of 2','Evidence register and reading order' if part==1 else 'Historical sources and image provenance','[Sxx] references in the report map to copied records in the reference ZIP. manifest.json gives original absolute paths, byte counts and SHA-256 hashes.')
    for k,num in enumerate(ids):
        sid=f'S{num:02d}';r=record(sid);x=M+(k//7)*(COL+G);z=y-(k%7)*54
        p(f'<b>{sid}</b> / {html.escape(Path(r["original"]).name)}',x,z,COL,'small',gap=2)
        p(source_desc[sid],x,z-14,COL,'tiny',gap=0)
    if part==2:
        p('Image provenance: F01/F04 are user screenshots; F02/F15-F22 are current actual WebGL captures; F03 is the historical accepted Samsung browser capture; F05 is the saved Codex Nikon source/model sheet; F06-F10 are controlled diagnostic renders; F11 is mesh/camera plotting; F12 is matched-photo evidence; F13-F14 are original Samsung photos.',M,110,CW,'tiny')
        p('Chat provenance: codex-nikon-provenance.json contains relevant archived Codex messages and thread IDs. Paths and image captions are indexed in manifest.json. Report opinions and the future plan are Codex recommendations, not completed experiments or external architectural approval.',M,73,CW,'tiny')

c.save()
(BASE/'layout_checks.json').write_text(json.dumps({'page_count':page,'titles':titles,'elements':checks},indent=2),encoding='utf-8')

# Store report-facing prose context and provenance with the reference images.
shutil.copy2(BASE/'codex-nikon-provenance.json',PACK/'codex-nikon-provenance.json')
(PACK/'REPORT_READ_FIRST.txt').write_text('''This reference pack accompanies Gemini_Argon_Reconstruction_Architecture_Report_2026-10-27.pdf.
The PDF is the narrative handoff and includes every image in this pack.
Use manifest.json to map image/record identifiers to original absolute paths and hashes.
The current verdict is PARTIAL visual quality. Proposals are not completed processing.
Nikon selection is Codex native-camera-kitchen-034, quality rejected, not later other-agent variants.
S11 is superseded preliminary evidence with a duplicated pair; do not quote its 36 rows as independent matches.
''',encoding='utf-8')
archive=OUT/'Gemini_Argon_Reference_Images_and_Evidence_2026-10-27.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for path in sorted(PACK.rglob('*')):
        if path.is_file():z.write(path,path.relative_to(PACK).as_posix())
print(json.dumps({'pdf':str(PDF),'pages':page,'pdf_bytes':PDF.stat().st_size,'reference_zip':str(archive),'zip_bytes':archive.stat().st_size},indent=2))
