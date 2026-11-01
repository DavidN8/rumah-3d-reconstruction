from pathlib import Path
import hashlib, json, re, sys
from pypdf import PdfReader
import pdfplumber
import report_author as a

p=a.OUT
reader=PdfReader(str(p))
texts=[page.extract_text() or '' for page in reader.pages]
full='\n'.join(texts)
normal=re.sub(r'\s+','',full)
missing=[]
for group,files in a.CODE_GROUPS:
    for f in files:
        source=f.read_text(encoding='utf-8-sig')
        for line_no,line in enumerate(source.splitlines(),1):
            line=line.expandtabs(4).encode('ascii','backslashreplace').decode()
            for i in range(0,len(line),157):
                part=re.sub(r'\s+','',line[i:i+157])
                if len(part)>=25 and part not in normal:
                    missing.append({'file':f.name,'line':line_no,'fragment':line[i:i+157]})
hard_bounds=[];margin_bounds=[];page_info=[];empty=[];blank_body=[]
with pdfplumber.open(p) as pdf:
    for i,page in enumerate(pdf.pages,1):
        text=texts[i-1]
        if len(text)<130:empty.append(i)
        body_chars=[c for c in page.chars if 35 < c['top'] < page.height-35 and not c['text'].isspace()]
        if len(body_chars)<20 and not page.images:blank_body.append(i)
        for char in page.chars:
            if char['text'].isspace():continue
            if char['x0']<-.1 or char['x1']>page.width+.1 or char['top']<-.1 or char['bottom']>page.height+.1:
                hard_bounds.append({'page':i,'text':char['text'],'x0':char['x0'],'x1':char['x1'],'top':char['top'],'bottom':char['bottom']})
            if 35<char['top']<page.height-35 and (char['x0']<38 or char['x1']>page.width-37):
                margin_bounds.append({'page':i,'text':char['text'],'x0':char['x0'],'x1':char['x1']})
        page_info.append({'page':i,'width':page.width,'height':page.height,
                          'characters':len(page.chars),'image_objects':len(page.images),
                          'first_text':text[:190]})
outline=reader.outline
must=['Current acceptance status: failed','485 x 485','20,000','30,351,100','2,366,966',
      'No completed clean-from-seed','Appendix A','Appendix B','Appendix C','Appendix D',
      'photo_bake_agent.py','foreground_masks.py','64.657%','18.934%']
missing_terms=[s for s in must if re.sub(r'\s+','',s) not in normal]
report={'pdf':str(p),'pages':len(reader.pages),'bytes':p.stat().st_size,
        'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'hard_bounds':hard_bounds,
        'body_margin_violations':margin_bounds,'code_fragments_missing':missing,
        'missing_required_terms':missing_terms,'low_text_pages':empty,'blank_body_pages':blank_body,
        'attachments':list(reader.attachments),'outline_top_entries':len(outline),
        'replacement_glyph_count':full.count('\ufffd')+full.count('\u25a0'),
        'page_info':page_info}
Path(a.TMP/'validation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
Path(a.TMP/'extracted.txt').write_text(full,encoding='utf-8')
print(json.dumps({k:v for k,v in report.items() if k!='page_info'},indent=2))
if hard_bounds or missing or missing_terms or blank_body or report['attachments'] or report['replacement_glyph_count']:
    raise SystemExit(1)
