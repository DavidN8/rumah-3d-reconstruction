from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
from pypdf import PdfReader
import json
root=Path(__file__).parent
pages=sorted((root/'rendered').glob('page-*.png'))
font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',18)
for start in range(0,len(pages),4):
    sheet=Image.new('RGB',(1700,1250),'#bbc5cb');d=ImageDraw.Draw(sheet)
    for k,path in enumerate(pages[start:start+4]):
        a=Image.open(path).convert('RGB');a.thumbnail((840,594));x=10+(k%2)*845;y=34+(k//2)*620;sheet.paste(a,(x,y));d.text((x,y-24),f'Page {start+k+1:02d}',font=font,fill='#122d3f')
    sheet.save(root/f'qa-sheet-{start//4+1}.png')
pdf=root.parents[1]/'outputs/Gemini_Argon_iPhone_Recovery_Verification_2026-10-27.pdf'
r=PdfReader(pdf);texts=[p.extract_text() or '' for p in r.pages]
(root/'text-extraction.txt').write_text('\n\n'.join(texts),encoding='utf-8')
print(json.dumps({'pages':len(r.pages),'words':sum(len(t.split()) for t in texts),'rendered_pages':len(pages),'sheets':(len(pages)+3)//4,'empty_pages':[i+1 for i,t in enumerate(texts) if len(t)<40]}))
