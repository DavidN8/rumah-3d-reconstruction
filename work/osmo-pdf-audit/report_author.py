"""Single-PDF forensic report. This script never starts reconstruction or deployment."""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import hashlib, io, json, math, os, re, struct, sys, textwrap, urllib.request
from xml.sax.saxutils import escape
from PIL import Image as PILImage, ImageDraw
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (BaseDocTemplate, PageTemplate, Frame, Paragraph,
    Spacer, PageBreak, NextPageTemplate, Table, TableStyle, Image, Flowable,
    KeepTogether, CondPageBreak)
from reportlab.platypus.tableofcontents import TableOfContents
from reportlab.graphics.shapes import Drawing, Rect, String, Line, Polygon

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
TMP=ROOT/'tmp/pdfs/osmo-processing-audit'
OUT=ROOT/'outputs/Osmo_Video_to_Mesh_Processing_Audit_2026-10-31.pdf'
DATA=Path(r'C:/Users/bombe/OneDrive/Documents/ChatGPT/Ruang Kamare/roomscan-reconstruction/data')
CAP=DATA/'20261031_OSMO360'
LITE=CAP/'lite-v1'
REC=CAP/'recovery-v2'
RT=DATA/'20261019_095800/runtime/spirula'
W=ROOT/'work'
WEB=W/'osmo-web-20261031-v3'
QA=W/'osmo-improve-20261031'
FMT=W/'osmo-format-20261031'
SRC=W/'osmo-reconstruct-20261031'
NOW=datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=7),'Asia/Jakarta'))
NAVY=colors.HexColor('#17324d')
TEAL=colors.HexColor('#087e8b')
RED=colors.HexColor('#a83d32')
INK=colors.HexColor('#233040')
GREY=colors.HexColor('#58697a')
PALE=colors.HexColor('#edf4f7')
EDGE=colors.HexColor('#ccd9e1')
PAGEW,PAGEH=A4
M=45
CW=PAGEW-2*M
STORY=[]
EVIDENCE=[]
HEADINGS=[]
FIG_COUNT=0

def load(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for block in iter(lambda:f.read(4*1024*1024),b''):h.update(block)
    return h.hexdigest()
def txt(x):
    return str(x).replace('\u2011','-').replace('\u2013','-').replace('\u2014',' - ').replace('\u00a0',' ')
def safe(x):return escape(txt(x))
def amount(n):return f'{n:,}'
def source(p,label=None):
    p=Path(p)
    if not p.is_file():raise FileNotFoundError(p)
    for row in EVIDENCE:
        if row['path']==str(p.resolve()):return row['id']
    row={'id':f'E{len(EVIDENCE)+1:02d}','path':str(p.resolve()),'label':label or p.name,
         'bytes':p.stat().st_size,'sha256':sha(p)}
    EVIDENCE.append(row);return row['id']

for name,file in [('Audit','arial.ttf'),('AuditBold','arialbd.ttf'),
                  ('AuditItalic','ariali.ttf'),('Code','consola.ttf')]:
    pdfmetrics.registerFont(TTFont(name,str(Path('C:/Windows/Fonts')/file)))
pdfmetrics.registerFontFamily('Audit',normal='Audit',bold='AuditBold',italic='AuditItalic',boldItalic='AuditBold')
ST=getSampleStyleSheet()
ST.add(ParagraphStyle('AuditBody',fontName='Audit',fontSize=10.1,leading=14.25,
    textColor=INK,spaceAfter=7.5,allowWidows=0,allowOrphans=0))
ST.add(ParagraphStyle('AuditSmall',parent=ST['AuditBody'],fontSize=8.4,leading=11.4,spaceAfter=5))
ST.add(ParagraphStyle('AuditCaption',parent=ST['AuditSmall'],fontSize=8.3,leading=11.1,textColor=GREY,spaceBefore=5,spaceAfter=10))
ST.add(ParagraphStyle('AuditH1',fontName='AuditBold',fontSize=20.4,leading=25,
    textColor=NAVY,spaceBefore=3,spaceAfter=14,keepWithNext=True))
ST.add(ParagraphStyle('AuditH2',fontName='AuditBold',fontSize=12.5,leading=16.6,
    textColor=TEAL,spaceBefore=13,spaceAfter=7,keepWithNext=True))
ST.add(ParagraphStyle('AuditH3',fontName='AuditBold',fontSize=10.5,leading=14,
    textColor=NAVY,spaceBefore=9,spaceAfter=5,keepWithNext=True))
ST.add(ParagraphStyle('AuditTitle',fontName='AuditBold',fontSize=28,leading=33,textColor=NAVY,spaceAfter=18))
ST.add(ParagraphStyle('AuditDeck',fontName='Audit',fontSize=13.2,leading=18.8,textColor=GREY,spaceAfter=16))
ST.add(ParagraphStyle('Cell',parent=ST['AuditSmall'],fontSize=8.1,leading=10.6,spaceAfter=0))
ST.add(ParagraphStyle('CellHead',parent=ST['Cell'],fontName='AuditBold',textColor=colors.white))
ST.add(ParagraphStyle('TOC0',fontName='AuditBold',fontSize=9.6,leading=14.2,textColor=NAVY,spaceBefore=5,leftIndent=0,firstLineIndent=0))
ST.add(ParagraphStyle('TOC1',fontName='Audit',fontSize=8.1,leading=11.8,textColor=INK,leftIndent=13,firstLineIndent=0))

def P(s,style='AuditBody'):
    q=Paragraph(txt(s),ST[style]);STORY.append(q);return q
def para(s,style='AuditBody'):return Paragraph(txt(s),ST[style])
def heading(s,level=1,new=False):
    if new:page()
    p=Paragraph(safe(s),ST['AuditH1' if level==1 else 'AuditH2' if level==2 else 'AuditH3'])
    if level<=2:
        p.audit_key=f'section-{len(HEADINGS)+1}'
        p.audit_level=level-1
        p.audit_title=txt(s)
        HEADINGS.append({'key':p.audit_key,'title':txt(s),'level':level-1})
    STORY.append(p);return p
def gap(n=8):STORY.append(Spacer(1,n))
def page():
    # A trailing spacer at a full frame can otherwise consume a blank page.
    while STORY and isinstance(STORY[-1],Spacer):STORY.pop()
    STORY.append(PageBreak())
def callout(title,body,kind='info'):
    color=RED if kind=='risk' else TEAL
    cell=[para(f'<b>{safe(title)}</b>','AuditSmall'),para(body,'AuditSmall')]
    t=Table([[cell]],colWidths=[CW],hAlign='LEFT')
    t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),colors.HexColor('#fff1ec') if kind=='risk' else PALE),
        ('BOX',(0,0),(-1,-1),.6,EDGE),('LINEBEFORE',(0,0),(0,-1),3,color),
        ('LEFTPADDING',(0,0),(-1,-1),12),('RIGHTPADDING',(0,0),(-1,-1),12),
        ('TOPPADDING',(0,0),(-1,-1),9),('BOTTOMPADDING',(0,0),(-1,-1),6)]))
    STORY.append(t);gap(10)
def table(headers,rows,widths=None,padding=6):
    widths=widths or [CW/len(headers)]*len(headers)
    data=[[para(safe(h),'CellHead') for h in headers]]
    for row in rows:data.append([para(str(v),'Cell') for v in row])
    t=Table(data,colWidths=widths,repeatRows=1,hAlign='LEFT')
    t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),NAVY),
        ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#f1f5f7')]),
        ('VALIGN',(0,0),(-1,-1),'TOP'),('LINEBELOW',(0,0),(-1,0),.7,NAVY),
        ('LINEBELOW',(0,1),(-1,-1),.3,EDGE),('LEFTPADDING',(0,0),(-1,-1),6),
        ('RIGHTPADDING',(0,0),(-1,-1),6),('TOPPADDING',(0,0),(-1,-1),padding),
        ('BOTTOMPADDING',(0,0),(-1,-1),padding)]))
    STORY.append(t);gap(9);return t
def figure(path,title,caption,maxh=330):
    global FIG_COUNT
    p=Path(path);source(p,title)
    im=PILImage.open(p);w,h=im.size
    scale=min(CW/w,maxh/h)
    STORY.append(Image(str(p),width=w*scale,height=h*scale,hAlign='CENTER'))
    FIG_COUNT+=1
    P(f'<b>Figure {FIG_COUNT}. {safe(title)}</b><br/>{caption}','AuditCaption')
def panel_grid(panels,title,caption):
    global FIG_COUNT
    cells=[]
    for i,(p,label) in enumerate(panels):
        im=PILImage.open(p);w,h=im.size
        size=(CW-12)/2
        cells.append([Image(str(p),width=size,height=size*h/w),para(label,'AuditCaption')])
    rows=[cells[:2],cells[2:]]
    t=Table(rows,colWidths=[(CW-12)/2]*2,hAlign='LEFT')
    t.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),3),
        ('RIGHTPADDING',(0,0),(-1,-1),3),('TOPPADDING',(0,0),(-1,-1),2),('BOTTOMPADDING',(0,0),(-1,-1),3)]))
    STORY.append(t);FIG_COUNT+=1
    P(f'<b>Figure {FIG_COUNT}. {safe(title)}</b><br/>{caption}','AuditCaption')

class CodeBlock(Flowable):
    def __init__(self,rows,label='',font=7.2,leading=9.2):
        Flowable.__init__(self);self.rows=rows;self.label=label;self.font=font;self.leading=leading
    def wrap(self,availW,availH):
        self.width=availW;self.height=22+len(self.rows)*self.leading;return self.width,self.height
    def split(self,availW,availH):
        n=int((availH-22)/self.leading)
        if n<4:return []
        if n>=len(self.rows):return [self]
        return [CodeBlock(self.rows[:n],self.label,self.font,self.leading),
                CodeBlock(self.rows[n:],self.label.removesuffix(' (continued)')+' (continued)',self.font,self.leading)]
    def draw(self):
        c=self.canv;c.setFillColor(colors.HexColor('#f3f6f8'));c.rect(0,0,self.width,self.height,fill=1,stroke=0)
        c.setStrokeColor(EDGE);c.line(29,5,29,self.height-17)
        c.setFont('Audit',7);c.setFillColor(GREY)
        c.drawString(6,self.height-10,self.label[:170])
        y=self.height-21
        for number,line in self.rows:
            c.setFont('Code',self.font);c.setFillColor(GREY);c.drawRightString(25,y,str(number))
            c.setFillColor(INK);c.drawString(34,y,line);y-=self.leading
def code_text(text,label='',start=1,width=157):
    rows=[]
    for number,line in enumerate(text.splitlines(),start):
        line=line.expandtabs(4).encode('ascii','backslashreplace').decode('ascii')
        if not line:rows.append((number,''));continue
        for j in range(0,len(line),width):rows.append((number if j==0 else '+',line[j:j+width]))
    STORY.append(CodeBlock(rows,label));gap(9)
def code_file(p,label=None,first=None,last=None):
    p=Path(p);s=source(p);text=p.read_text(encoding='utf-8-sig')
    lines=text.splitlines();title=label or p.name
    heading(title,2)
    mode='Complete file' if first is None else f'Exact excerpt, source lines {first}-{last}'
    P(f'{safe(mode)}. [{s}] {safe(str(p))}<br/>SHA-256: {sha(p)}','AuditSmall')
    if first is not None:text='\n'.join(lines[first-1:last])
    code_text(text,p.name,first or 1)
def arrow(d,x1,y1,x2,y2,color=TEAL):
    d.add(Line(x1,y1,x2,y2,strokeColor=color,strokeWidth=1.3))
    a=math.atan2(y2-y1,x2-x1);n=5
    d.add(Polygon([x2,y2,x2-n*math.cos(a-.5),y2-n*math.sin(a-.5),x2-n*math.cos(a+.5),y2-n*math.sin(a+.5)],fillColor=color,strokeColor=color))
def box(d,x,y,w,h,title,lines,color=TEAL):
    d.add(Rect(x,y,w,h,rx=6,ry=6,fillColor=PALE,strokeColor=EDGE,strokeWidth=.8))
    d.add(Rect(x,y+h-4,w,4,fillColor=color,strokeColor=color))
    d.add(String(x+9,y+h-20,title,fontName='AuditBold',fontSize=10,fillColor=NAVY))
    for j,line in enumerate(lines):d.add(String(x+9,y+h-35-j*11,line,fontName='Audit',fontSize=8.5,fillColor=INK))
def pipeline():
    d=Drawing(CW,570);bw=(CW-26)/2;bh=66
    blocks=[
      (0,500,'01  Native OSV video',['Two 3840-square fisheye streams','65.231833 s; 1955 frames per lens']),
      (bw+26,500,'02  JPEG selection',['fps=2; scale to 1920 x 1920','130 synchronized pairs retained']),
      (bw+26,400,'03  Masks + calibration',['Circular border; manual person outlines','Factory KB5 -> native KB4 approximation']),
      (0,400,'04  Sparse reconstruction',['244 accepted images; 125,862 points','One rigid scene; alternate alignment isolated']),
      (0,300,'05  Learned geometry priors',['MoGe-2: 8 faces of 485 x 485 per image','209 affine fits -> 175 scale-only depth maps']),
      (bw+26,300,'06  Gaussian optimization',['196,461-point seed; resumed lineage','20k affine -> 40k trusted -> 50k refined']),
      (bw+26,200,'07  Surface extraction',['Sample Gaussians; Delaunay; occupancy','2,577,478 faces before support filtering']),
      (0,200,'08  Spatial support filter',['V4 probe + 25,676 sparse points','2,366,966 retained faces; no vertex motion']),
      (0,100,'09  Photographic UV bake',['Later full 3840 decode; 4096 atlas','Masks, first-hit tests, consensus, mild gain']),
      (bw+26,100,'10  GLB delivery packing',['Meshopt high; position16 / normal8 / UV12','30.351 MB; no additional simplification']),
      (bw+26,0,'11  Website choice gate',['Three cards with compressed sizes','No model transfer until Open model']),
      (0,0,'12  Acceptance failure',['Technical checks improved; visible defects remain','User rejected the reconstruction quality'])]
    for x,y,title,lines in blocks:box(d,x,y,bw,bh,title,lines,RED if title.startswith('12') else TEAL)
    for a,b in [(0,1),(1,2),(2,3),(3,4),(4,5),(5,6),(6,7),(7,8),(8,9),(9,10),(10,11)]:
        x,y=blocks[a][:2];xx,yy=blocks[b][:2]
        if y==yy:
            arrow(d,x+bw if xx>x else x,y+bh/2,xx if xx>x else xx+bw,yy+bh/2)
        else:arrow(d,x+bw/2,y,xx+bw/2,yy+bh)
    STORY.append(d);gap(8)
def lineage():
    d=Drawing(CW,185);w=(CW-24)/3
    box(d,0,110,w,65,'Pilot: direct fisheye',['20k steps; 1M cap','Separate pilot branch','Not final-model parent'])
    box(d,0,19,w,72,'Rectified precursor',['20k saved checkpoint','2.5M cap; affine depth','Seed uses affine fits'],RED)
    box(d,w+12,19,w,72,'Trusted v3',['Resume 20k -> 40k','175 scale-only depths','Existing seed/state inherited'])
    box(d,2*(w+12),19,w,72,'Surface v4',['Resume 40k -> 50k','3M cap; stronger priors','Selected final lineage'])
    arrow(d,w,55,w+12,55);arrow(d,2*w+12,55,2*w+24,55)
    d.add(String(0,3,'No completed clean-from-seed training run used trusted scale-only priors throughout.',fontName='AuditBold',fontSize=9.1,fillColor=RED))
    STORY.append(d);gap(9)
def transparency_chart():
    d=Drawing(CW,160);x=155;scale=(CW-x-35)/3
    rows=[('Original 17.7 MB',2.747,TEAL),('Cull-off diagnostic',0,RED),
          ('Dense 47.4 MB',2.084,TEAL),('Final 30.4 MB',1.320,TEAL)]
    for j,(lab,val,col) in enumerate(rows):
        y=130-j*32
        d.add(String(0,y+3,lab,fontName='Audit',fontSize=9,fillColor=INK))
        d.add(Rect(x,y,max(.8,val*scale),15,fillColor=col,strokeColor=col))
        d.add(String(x+val*scale+6,y+3,f'{val:.3f}%',fontName='AuditBold',fontSize=9,fillColor=col))
    STORY.append(d)
    P('Measured transparent viewport pixels in six fixed 400 x 400 views. Zero in the cull-off test did not mean correct geometry: that test restored large unsupported shells.','AuditCaption')

class AuditDoc(BaseDocTemplate):
    def __init__(self,p):
        super().__init__(str(p),pagesize=A4,leftMargin=M,rightMargin=M,topMargin=48,bottomMargin=43,
            title='Osmo video-to-mesh processing audit',author='Codex - reconstruction audit',
            subject='User-rejected Osmo reconstruction: actual pipeline, code, evidence and unresolved processing issues')
        self.addPageTemplates([
            PageTemplate(id='portrait',pagesize=A4,frames=[Frame(M,43,CW,PAGEH-91,id='p',leftPadding=0,rightPadding=0,topPadding=0,bottomPadding=0)],onPage=self.chrome),
            PageTemplate(id='code',pagesize=landscape(A4),frames=[Frame(40,35,landscape(A4)[0]-80,landscape(A4)[1]-76,id='c',leftPadding=0,rightPadding=0,topPadding=0,bottomPadding=0)],onPage=self.chrome)])
    def chrome(self,c,doc):
        w,h=c._pagesize
        c.saveState();c.setStrokeColor(EDGE);c.setLineWidth(.5);c.line(40,h-30,w-40,h-30)
        c.setFont('Audit',7.6);c.setFillColor(GREY)
        c.drawString(40,h-21,'OSMO360 | VIDEO-TO-MESH PROCESSING AUDIT')
        c.drawRightString(w-40,h-21,'31 OCT 2026 | FAILED VISUAL ACCEPTANCE')
        c.line(40,26,w-40,26);c.drawString(40,15,'Evidence snapshot; no new reconstruction performed for this PDF')
        c.drawRightString(w-40,15,f'{doc.page}')
        c.restoreState()
    def afterFlowable(self,flow):
        if getattr(flow,'audit_key',None):
            self.canv.bookmarkPage(flow.audit_key)
            self.canv.addOutlineEntry(flow.audit_title,flow.audit_key,level=flow.audit_level,closed=True)
            self.notify('TOCEntry',(flow.audit_level,flow.audit_title,self.page,flow.audit_key))

def prep_assets():
    TMP.mkdir(parents=True,exist_ok=True);OUT.parent.mkdir(parents=True,exist_ok=True)
    # Exact panel crops from saved, identically calibrated 600px audit renders.
    base=PILImage.open(QA/'baseline-consensus-render-check.jpg').convert('RGB')
    final=PILImage.open(QA/'v4-final-texture-render-check.jpg').convert('RGB')
    assert base.size==(3600,1896) and final.size==(3600,2528)
    source(QA/'baseline-consensus-render-check.jpg','Original/texture-only proof render sheet')
    source(QA/'v4-final-texture-render-check.jpg','Final native/no-gain/gain render sheet')
    for k in range(6):
        for name,im,row in [('source',base,0),('original',base,1),('native-v4',final,1),('final',final,3)]:
            im.crop((600*k,row*632+32,600*(k+1),row*632+632)).save(TMP/f'view{k+1}-{name}.jpg',quality=96,subsampling=0)
    # Mask overlay is a diagnostic visualization, not an edited training image.
    full=PILImage.open(REC/'source-full/images/cam0/frame_000041.jpg').convert('RGB')
    mask=PILImage.open(REC/'source-full/masks/cam0/frame_000041.png').convert('L')
    thumb=full.resize((900,900),PILImage.Resampling.LANCZOS)
    m=mask.resize((900,900),PILImage.Resampling.NEAREST)
    tint=PILImage.new('RGB',thumb.size,(210,25,35))
    m=m.point(lambda v:120 if v<128 else 0)
    overlay=PILImage.composite(tint,thumb,m)
    thumb.save(TMP/'mirror-fisheye.jpg',quality=94)
    overlay.save(TMP/'mirror-mask-overlay.jpg',quality=94)
    PILImage.open(LITE/'dataset/masks/cam0/frame_000041.png').convert('RGB').save(TMP/'mirror-mask.jpg',quality=96)
    PILImage.open(LITE/'review/photos/osmo-upright-03-frame_000041.jpg').convert('RGB').save(TMP/'mirror-upright.jpg',quality=94)

def live_snapshot():
    b=load(WEB/'build-report.json')
    result={'requested_at':NOW.isoformat(),'model_download_performed':False}
    try:
        req=urllib.request.Request('https://rumah.shizuku.rest/',headers={'User-Agent':'Rumah processing audit report','Accept-Encoding':'identity'})
        with urllib.request.urlopen(req,timeout=20) as response:
            html=response.read();result.update(http_status=response.status,html_bytes=len(html),
                contains_chooser=b'id="model-chooser"' in html,contains_final_bundle=b['bundleName'].encode() in html)
        req=urllib.request.Request('https://rumah.shizuku.rest/'+b['manifestName'],headers={'User-Agent':'Rumah processing audit report','Accept-Encoding':'identity'})
        with urllib.request.urlopen(req,timeout=20) as response:
            raw=response.read();result.update(manifest_status=response.status,manifest_bytes=len(raw),
                manifest_matches_saved_build=hashlib.sha256(raw).hexdigest()==next(x['sha256'] for x in b['deploymentManifest'] if x['path']==b['manifestName']))
    except Exception as exc:result['read_only_recheck_error']=str(exc)
    (TMP/'live-report-snapshot.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    return result

CODE_GROUPS=[
('A1. Native video preparation and calibration',[
 LITE/'scripts/prepare_frames.py',LITE/'scripts/foreground_masks.py',LITE/'scripts/verify_frozen_masks.py',
 FMT/'decode_calibration.py',FMT/'calib_slots.py',FMT/'fit_kb4.py']),
('A2. Sparse geometry, priors and initial seeding',[
 SRC/'run_stage.py',SRC/'normalize_sfm.py',SRC/'seed_fisheye.py',SRC/'align_depths.py',SRC/'refit_trusted_scale.py',SRC/'resume_trusted.py']),
('A3. The final refinement and support filter',[
 QA/'qa-surface-v4.py',QA/'extract_candidate.py',QA/'qa-support-filter.py',QA/'qa-extract-full.py']),
('A4. Actual-photo texture construction',[
 QA/'photometric_audit_agent.py',QA/'photo_bake_agent.py',SRC/'export_web_cameras.py']),
('A5. Packing and reconstruction diagnostics',[
 WEB/'pack-osmo.mjs',QA/'qa-geometry.py',QA/'qa-paired-comparison.py',QA/'geometry_audit_agent.py',QA/'photo_render_check_agent.py']),
('A6. Website choice, loading and rendering',[
 WEB/'choice-core.js',WEB/'chooser.js',WEB/'delivery-policy.js',WEB/'loader-core.js',WEB/'room-shell.html',WEB/'room-viewer.js',WEB/'build.mjs']),
('A7. Publishing and public verification',[
 WEB/'prepare_deploy.py',WEB/'verify_public.py'])]

def append_code():
    STORY.extend([NextPageTemplate('code'),PageBreak()])
    heading('Appendix A. Executed helper source and website code')
    P('The following are current on-disk source snapshots, printed in full. They are historical implementation evidence, not a safe run-all sequence. Some wrappers have fixed paths, refusal guards or mutable branch names. The captured argument vectors in Appendix B and saved configurations take precedence over a wrapper\'s current defaults. No reconstruction, training, segmentation or deployment code was executed to produce this report.')
    P('Display convention: original line numbers are printed; a + marks the continuation of a long source line. Tabs expand to four spaces. Non-ASCII characters are displayed as backslash Unicode escapes where needed to keep code legible. Full SHA-256 values refer to the original file bytes, not this typeset presentation. To rerun, recover the original text/paths and dependencies; do not treat PDF line wrapping as executable syntax. The pretrained weights, source media, complete native engine and binary GLB are not embedded.')
    for group,paths in CODE_GROUPS:
        page();heading(group)
        for p in paths:code_file(p)
    page();heading('A8. Native engine excerpts that explain observed behavior')
    P('These are exact line-range excerpts from the bundled Spirula source tree (GPLv3 in the supplied distribution), not the entire engine. The binary fingerprint is recorded separately. I did not establish a reproducible build linking this source tree to the exact installed binary, so source inspection and runtime logs are kept distinct.')
    code_file(RT/'source/src/app/cli/mesh_main.cpp','Native mesh CLI: effective cleanup default',252,271)
    code_file(RT/'source/src/mesh/MeshingHost.cpp','Native cull: an unseen vertex drops every incident face',1807,1855)
    code_file(RT/'source/src/app/cli/mesh_main.cpp','Native export loads DC colors, not higher-order SH',376,435)
    code_file(RT/'source/src/mesh/MeshingRasterHost.cpp','Native raster input contains learned Gaussian DC, not source RGB',151,184)
    code_file(RT/'source/src/mesh/MeshingRasterHost.cpp','Native learned-color render call',199,241)
    code_file(RT/'source/src/mesh/Meshing.h','Native geometry defaults and hole-fill criteria',31,95)

def append_records():
    page();heading('Appendix B. Captured commands and final configuration')
    P('Argument arrays below are copied from saved stage records. They distinguish the command actually executed from later edits to wrapper files. Paths are local to this Windows workspace. JSON backslashes and Python array layout are presentation, not PowerShell escaping.')
    entries=[
      ('Initial frame decode',LITE/'analysis/extract.json'),
      ('Accepted calibrated SfM',LITE/'analysis/sfm.json'),
      ('MoGe geometry generation',LITE/'analysis/geometry.json'),
      ('Direct-fisheye pilot training',LITE/'analysis/train-direct-fisheye-v1.json'),
      ('Rectified precursor training',LITE/'analysis/train-rectified-v2.json'),
      ('Trusted-depth resume to 40k',LITE/'analysis/train-trusted-v3.json'),
      ('Bounded surface refinement to 50k',REC/'analysis/train-surface-v4.json'),
      ('Final native textured extraction',REC/'analysis/v4-texture.json')]
    import pprint
    for title,p in entries:
        d=load(p);e=source(p,title)
        heading(title,2)
        fields={k:d[k] for k in ['status','exit_code','elapsed_seconds','source_checkpoint_step','target_step','maximum_additional_iterations'] if k in d}
        P(f'[{e}] {safe(p.name)} | '+safe(json.dumps(fields,ensure_ascii=True)),'AuditSmall')
        code_text(pprint.pformat(d.get('command',d),width=150,sort_dicts=False),title)
    for title,p in [('Actual SfM rig/calibration manifest',LITE/'analysis/sfm-manifest.json'),
      ('Final saved 50k TrainConfig',REC/'training/osmo-surface-v4/config.json'),
      ('Final saved scene transform',REC/'training/osmo-surface-v4/scene_transform.json'),
      ('Normalized COLMAP camera parameters',LITE/'dataset/sparse/0/cameras.txt'),
      ('Frame normalization provenance',LITE/'analysis/normalized-frame.json'),
      ('Final packed asset properties',WEB/'osmo-asset-report.json')]:
        code_file(p,title)
    page();heading('Appendix C. Evidence catalogue and fingerprints')
    P('These identifiers are referenced throughout the report. Each fingerprint binds the inspected local artifact. The original video/LRF import hashes are separately described as recorded-at-import, rather than falsely presented as newly rehashed media. The report includes the important findings, code and selected images directly; this catalogue is for traceability, not a request to open a ZIP.')
    for row in EVIDENCE.copy():
        P(f'<b>{row["id"]} | {safe(row["label"])}</b><br/>{safe(row["path"])}<br/>{row["bytes"]:,} bytes | SHA-256 {row["sha256"]}','AuditSmall')
    page();heading('Appendix D. Primary technical references')
    refs=[
      ('R1','COLMAP camera models','https://colmap.github.io/cameras.html','Supports the distinction between perspective and fisheye camera models. It does not validate this reconstruction.'),
      ('R2','COLMAP tutorial / rig terminology','https://colmap.github.io/tutorial','A rig groups cameras with constant relative pose; frames group simultaneous captures. The executed reconstruction was Spirula native SfM using COLMAP-style data.'),
      ('R3','OpenCV fisheye model','https://docs.opencv.org/4.2.0/db/d58/group__calib3d__fisheye.html','Reference polynomial convention. Our custom unit-ray helpers use atan2 for the wider-than-180-degree domain; backend equivalence still needs explicit verification.'),
      ('R4','Microsoft MoGe v2 source and evaluation','https://github.com/microsoft/MoGe/blob/main/moge/model/v2.py','Primary implementation context for inferred point maps, normals and metric-scale output; inference is not measured scene depth.'),
      ('R5','2D Gaussian Splatting, SIGGRAPH 2024','https://surfsplatting.github.io/','A surface-oriented alternative to consider only as a controlled pilot, not a method already run or a promise that it will fix this footage.')]
    for key,title,url,note in refs:
        P(f'<b>{key}. {safe(title)}</b><br/><link href="{escape(url)}" color="#087e8b">{escape(url)}</link><br/>{safe(note)}','AuditSmall')
    P('References checked 31 October 2026. External sources are used narrowly for terminology and proposed experiment context; all claims about the performed run rely on local logs, code and artifacts.')
    P('End of report. One PDF only. No source archive or ZIP is required to read the included code and visual evidence.','AuditSmall')

def main():
    prep_assets()
    snapshot=live_snapshot()
    # Check the exact delivered asset, without hydrating or rehashing the 1.16GB original video.
    asset=load(WEB/'osmo-asset-report.json')
    assert sha(asset['file'])==asset['sha256']
    source(Path(asset['file']),'Current final packed model (fresh local hash)')
    source(RT/'bin/spirula.exe','Installed native Spirula executable')
    from report_content import build_narrative
    build_narrative(sys.modules[__name__],snapshot)
    append_code()
    append_records()
    doc=AuditDoc(OUT)
    doc.multiBuild(STORY)
    from pypdf import PdfReader
    reader=PdfReader(str(OUT))
    inventory={'pdf':str(OUT),'pages':len(reader.pages),'bytes':OUT.stat().st_size,
        'sha256':sha(OUT),'created_local':NOW.isoformat(),'figures':FIG_COUNT,
        'code_files':sum(len(x[1]) for x in CODE_GROUPS),'evidence':EVIDENCE,
        'headings':HEADINGS,'live_snapshot':snapshot}
    (TMP/'build-audit.json').write_text(json.dumps(inventory,indent=2),encoding='utf-8')
    print(json.dumps({k:inventory[k] for k in ['pdf','pages','bytes','sha256','figures','code_files']},indent=2))
if __name__=='__main__':main()
