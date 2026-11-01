"""Verify the single report artifact, without touching reconstruction or hosting."""
from pathlib import Path
import hashlib,json,re
import pdfplumber
from pypdf import PdfReader

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
TMP=ROOT/'tmp/pdfs/osmo-ux-report'
audit=json.loads((TMP/'build-audit.json').read_text())
pdf=Path(audit['file'])
reader=PdfReader(str(pdf))
problems=[]
page_info=[]
texts=[]
with pdfplumber.open(pdf) as document:
    for index,page in enumerate(document.pages,1):
        words=page.extract_words()
        text=page.extract_text() or ''
        texts.append(text)
        if not words:
            problems.append({'page':index,'issue':'Empty text page'})
        for word in words:
            if word['x0']<22 or word['x1']>page.width-22 or word['top']<9 or word['bottom']>page.height-9:
                problems.append({'page':index,'issue':'Text outside safe bounds','word':word['text']})
        if any(char in text for char in ['\ufffd','\u25a0']):
            problems.append({'page':index,'issue':'Replacement or square glyph'})
        if not (TMP/f'final-page-{index:02d}.png').is_file():
            problems.append({'page':index,'issue':'Missing page raster'})
        page_info.append({'page':index,'chars':len(text),'words':len(words),'images':len(page.images),'size':[page.width,page.height]})
text='\n\n'.join(texts)
topics=['Executive finding and responsibility','What is actually being compared','Visual evidence: blur exists before compression','Why the dollhouse view is missing','Why the controls feel inconsistent','Current Osmo pipeline','Questions for Gemini Argon','Historical Nikon and Samsung comparison','Complete held-out score table','Processing code and viewer branches','Evidence, graph coverage and fingerprints']
missing=[topic for topic in topics if topic not in text]
if missing:
    problems.append({'issue':'Missing required topics','topics':missing})
if len(reader.pages)!=audit['pages']:
    problems.append({'issue':'Page count differs from build record'})
for number in range(1,68):
    if f'E{number:02d} |' not in text:
        problems.append({'issue':'Missing evidence catalogue entry','entry':number})
sha=hashlib.sha256(pdf.read_bytes()).hexdigest()
if sha!=audit['sha256']:
    problems.append({'issue':'Hash differs from build record'})
result={
    'pdf':str(pdf),'pages':len(reader.pages),'renderedPages':len(reader.pages),
    'bytes':pdf.stat().st_size,'sha256':sha,'requiredTopicsPresent':not missing,
    'evidenceEntries':67,'problems':problems,'pageInfo':page_info,
    'visualReview':{
        'initialDraft':'All 75 pages inspected in nine contact sheets; no clipping or overlap. Two layout improvements applied.',
        'finalChanges':'TOC consolidated onto one page; training command begins with its appendix introduction.',
        'finalFullPageInspection':[2,6,39,40,41,68,73],
        'status':'pending final full-page review'
    },
    'singlePdf':True,'reconstructionOrDeploymentStarted':False
}
(TMP/'text.txt').write_text(text,encoding='utf-8')
(TMP/'validation.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k not in ['pageInfo','visualReview']},indent=2))
if problems:
    raise SystemExit(1)
