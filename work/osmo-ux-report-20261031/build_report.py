"""Create the requested single PDF; never train or deploy a reconstruction."""
from pathlib import Path
from datetime import datetime,timezone,timedelta
import json,hashlib,math,textwrap,re
from xml.sax.saxutils import escape
from PIL import Image as PILImage
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4,landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import BaseDocTemplate,PageTemplate,Frame,Paragraph,Spacer,PageBreak,NextPageTemplate,Table,TableStyle,Image,Flowable,KeepTogether
from reportlab.platypus.tableofcontents import TableOfContents
from reportlab.graphics.shapes import Drawing,Rect,String,Line,Polygon

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
OUT=ROOT/'output/pdf/Osmo_Quality_Controls_and_Pipeline_Review_2026-10-31.pdf'
TMP=ROOT/'tmp/pdfs/osmo-ux-report';TMP.mkdir(parents=True,exist_ok=True)
A=json.loads((HERE/'evidence.json').read_text());STORY=[];HEADINGS=[];FIGURES=[]
PW,PH=A4;M=44;CW=PW-2*M;MODE='portrait'
NAVY=colors.HexColor('#153047');TEAL=colors.HexColor('#08787c');INK=colors.HexColor('#263747');GREY=colors.HexColor('#586b79');PALE=colors.HexColor('#eef4f6');EDGE=colors.HexColor('#cbd8df');RED=colors.HexColor('#a33d36')
for name,file in [('Body','arial.ttf'),('Bold','arialbd.ttf'),('Italic','ariali.ttf'),('Mono','consola.ttf')]:pdfmetrics.registerFont(TTFont(name,str(Path('C:/Windows/Fonts')/file)))
pdfmetrics.registerFontFamily('Body',normal='Body',bold='Bold',italic='Italic',boldItalic='Bold')
S={
 'body':ParagraphStyle('BodyP',fontName='Body',fontSize=10.3,leading=14.3,textColor=INK,spaceAfter=8,allowWidows=0,allowOrphans=0),
 'small':ParagraphStyle('Small',fontName='Body',fontSize=8.6,leading=11.6,textColor=INK,spaceAfter=6),
 'caption':ParagraphStyle('Caption',fontName='Body',fontSize=8.5,leading=11.4,textColor=GREY,spaceBefore=5,spaceAfter=12),
 'h1':ParagraphStyle('H1',fontName='Bold',fontSize=19,leading=23.5,textColor=NAVY,spaceAfter=13,keepWithNext=True),
 'h2':ParagraphStyle('H2',fontName='Bold',fontSize=12.3,leading=16,textColor=TEAL,spaceBefore=12,spaceAfter=7,keepWithNext=True),
 'title':ParagraphStyle('Title',fontName='Bold',fontSize=29,leading=34,textColor=NAVY,spaceAfter=16),
 'deck':ParagraphStyle('Deck',fontName='Body',fontSize=13,leading=18.8,textColor=GREY,spaceAfter=14),
 'cell':ParagraphStyle('Cell',fontName='Body',fontSize=8.7,leading=11.6,textColor=INK,spaceAfter=0),
 'head':ParagraphStyle('HeadCell',fontName='Bold',fontSize=8.7,leading=11.6,textColor=colors.white,spaceAfter=0),
 'toc':ParagraphStyle('TOC',fontName='Body',fontSize=9.6,leading=14.4,textColor=NAVY,leftIndent=0,firstLineIndent=0,spaceBefore=0),
}
def clean(value):
    return str(value).replace('\u2011','-').replace('\u2013','-').replace('\u2014',' - ').replace('\u00a0',' ').replace('\u2192',' -> ').replace('\u2019',"'").replace('\u2018',"'").replace('\u201c','"').replace('\u201d','"')
def safe(value):return escape(clean(value))
def para(value,style='body'):return Paragraph(clean(value),S[style])
def P(value,style='body'):STORY.append(para(value,style))
def cite(*keys):return '['+'; '.join(A['sources'][k]['id'] for k in keys)+']'
def gap(n=7):STORY.append(Spacer(1,n))
def page():
    while STORY and isinstance(STORY[-1],Spacer):STORY.pop()
    STORY.append(PageBreak())
def orientation(mode):
    global MODE
    MODE=mode;STORY.append(NextPageTemplate(mode));page()
def H(title,level=1,new=False):
    if new:page()
    p=para(safe(title),'h1' if level==1 else 'h2');p.audit_title=clean(title);p.audit_level=level-1;p.audit_key='section-'+str(len(HEADINGS)+1);HEADINGS.append({'title':title,'key':p.audit_key,'level':level-1});STORY.append(p)
def box(title,text,risk=False):
    t=Table([[[para('<b>'+safe(title)+'</b>','small'),para(text,'small')]]],colWidths=[CW])
    t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),colors.HexColor('#fff2ed') if risk else PALE),('LINEBEFORE',(0,0),(0,-1),3,RED if risk else TEAL),('BOX',(0,0),(-1,-1),.5,EDGE),('LEFTPADDING',(0,0),(-1,-1),11),('RIGHTPADDING',(0,0),(-1,-1),11),('TOPPADDING',(0,0),(-1,-1),9),('BOTTOMPADDING',(0,0),(-1,-1),6)]));STORY.append(t);gap(9)
def table(headers,rows,widths=None,small=False):
    widths=widths or [CW/len(headers)]*len(headers)
    data=[[para(safe(x),'head') for x in headers]]+[[para(str(x),'small' if small else 'cell') for x in row] for row in rows]
    t=Table(data,colWidths=widths,repeatRows=1,hAlign='LEFT');t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),NAVY),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,PALE]),('VALIGN',(0,0),(-1,-1),'TOP'),('LINEBELOW',(0,0),(-1,0),.6,NAVY),('LINEBELOW',(0,1),(-1,-1),.25,EDGE),('LEFTPADDING',(0,0),(-1,-1),6),('RIGHTPADDING',(0,0),(-1,-1),6),('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6)]));STORY.append(t);gap(8)
def fig(key,title,caption,maxh=340):
    path=Path(A['images'][key]['path']) if key in A['images'] else Path(key)
    im=PILImage.open(path);w,h=im.size;maxw=(landscape(A4)[0]-80) if MODE=='landscape' else CW;s=min(maxw/w,maxh/h)
    no=len(FIGURES)+1;FIGURES.append({'number':no,'title':title,'path':str(path)})
    STORY.append(KeepTogether([Image(str(path),width=w*s,height=h*s,hAlign='CENTER'),para(f'<b>Figure {no}. {safe(title)}</b><br/>'+caption,'caption')]))
def flow(title,steps):
    height=len(steps)*72-9;d=Drawing(CW,height)
    for i,(label,detail) in enumerate(steps):
        y=height-63-i*72;d.add(Rect(20,y,CW-40,63,rx=5,ry=5,fillColor=PALE,strokeColor=EDGE));d.add(String(31,y+43,f'{i+1:02d}  {label}',fontName='Bold',fontSize=10,fillColor=NAVY))
        for j,line in enumerate(detail):d.add(String(31,y+27-j*12,line,fontName='Body',fontSize=9,fillColor=INK))
        if i<len(steps)-1:
            x=CW/2;d.add(Line(x,y,x,y-8,strokeColor=TEAL));d.add(Polygon([x-3,y-5,x+3,y-5,x,y-9],fillColor=TEAL,strokeColor=TEAL))
    STORY.append(d);gap(8)
class CodeBlock(Flowable):
    def __init__(self,rows,label='',font=8.3,leading=10.8):Flowable.__init__(self);self.rows=rows;self.label=label;self.font=font;self.leading=leading
    def wrap(self,w,h):self.width=w;self.height=24+len(self.rows)*self.leading;return w,self.height
    def split(self,w,h):
        n=int((h-24)/self.leading)
        if n<4:return []
        if n>=len(self.rows):return [self]
        return [CodeBlock(self.rows[:n],self.label,self.font,self.leading),CodeBlock(self.rows[n:],self.label.replace(' (continued)','')+' (continued)',self.font,self.leading)]
    def draw(self):
        c=self.canv;c.setFillColor(PALE);c.rect(0,0,self.width,self.height,fill=1,stroke=0);c.setFont('Body',7.6);c.setFillColor(GREY);c.drawString(6,self.height-11,self.label[:120]);c.setStrokeColor(EDGE);c.line(31,5,31,self.height-18);y=self.height-24
        for number,line in self.rows:
            c.setFont('Mono',self.font);c.setFillColor(GREY);c.drawRightString(27,y,str(number));c.setFillColor(INK);c.drawString(37,y,line);y-=self.leading
def code(text,label='',start=1):
    width=147 if MODE=='landscape' else 94;rows=[]
    for number,line in enumerate(text.splitlines(),start):
        line=clean(line).expandtabs(4).encode('ascii','backslashreplace').decode('ascii');chunks=[line[i:i+width] for i in range(0,len(line),width)] or ['']
        rows.extend((number if i==0 else '+',v) for i,v in enumerate(chunks))
    STORY.append(CodeBlock(rows,label));gap(9)
def codefile(rel,title=None,first=None,last=None):
    path=HERE/'code'/rel;lines=path.read_text(encoding='utf-8-sig').splitlines();H(title or rel,2)
    digest=hashlib.sha256(path.read_bytes()).hexdigest();P(f'{safe(rel)} | '+('Complete file' if first is None else f'Exact source excerpt, lines {first}-{last}')+f'<br/>SHA-256 {digest}','small');code('\n'.join(lines if first is None else lines[first-1:last]),path.name,first or 1)
class Doc(BaseDocTemplate):
    def __init__(self,p):
        super().__init__(str(p),pagesize=A4,title='Osmo360 quality, controls and pipeline review - 31 October 2026',author='Codex',subject='User-rejected Osmo release; comparison with iPhone Fast/Lite, processing evidence, code, recommendations and open architectural questions')
        self.addPageTemplates([PageTemplate(id='portrait',pagesize=A4,frames=[Frame(M,44,CW,PH-91,id='portrait-frame',leftPadding=0,rightPadding=0,topPadding=0,bottomPadding=0)],onPage=self.chrome),PageTemplate(id='landscape',pagesize=landscape(A4),frames=[Frame(40,38,landscape(A4)[0]-80,landscape(A4)[1]-79,id='landscape-frame',leftPadding=0,rightPadding=0,topPadding=0,bottomPadding=0)],onPage=self.chrome)])
    def chrome(self,c,doc):
        w,h=c._pagesize;c.saveState();c.setStrokeColor(EDGE);c.line(40,h-29,w-40,h-29);c.setFillColor(GREY);c.setFont('Body',7.5);c.drawString(40,h-20,'OSMO360 | QUALITY, CONTROLS AND PIPELINE REVIEW');c.line(40,29,w-40,29);c.drawString(40,17,'31 OCT 2026 (UTC+7) | Codex -> Gemini Argon / Architect');c.drawRightString(w-40,17,str(doc.page));c.restoreState()
    def afterFlowable(self,f):
        if hasattr(f,'audit_title'):
            self.canv.bookmarkPage(f.audit_key);self.canv.addOutlineEntry(f.audit_title,f.audit_key,f.audit_level,closed=False)
            if f.audit_level==0:self.notify('TOCEntry',(0,f.audit_title,self.page,f.audit_key))
def main():
    from report_content import narrative,appendices
    narrative(__import__(__name__));appendices(__import__(__name__))
    doc=Doc(OUT);doc.multiBuild(STORY)
    from pypdf import PdfReader
    reader=PdfReader(str(OUT));audit={'file':str(OUT),'pages':len(reader.pages),'bytes':OUT.stat().st_size,'sha256':hashlib.sha256(OUT.read_bytes()).hexdigest(),'figures':FIGURES,'headings':HEADINGS,'evidenceCount':len(A['evidence']),'singlePdf':True,'reconstructionOrDeploymentStarted':False}
    (TMP/'build-audit.json').write_text(json.dumps(audit,indent=2));print(json.dumps({k:v for k,v in audit.items() if k not in ['figures','headings']},indent=2))
if __name__=='__main__':main()
