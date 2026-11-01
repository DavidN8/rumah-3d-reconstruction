from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps
import json
import sys

root = Path(__file__).resolve().parents[2]
tmp = root / 'tmp/pdfs/osmo-processing-audit'
render = sys.argv[1] if len(sys.argv)>1 else 'render'
pages = sorted((tmp / render).glob('page-*.png'))
dest = tmp / ('contact-sheets' if render=='render' else 'contact-sheets-approved')
dest.mkdir(exist_ok=True)
font = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 17)
for base in range(0, len(pages), 20):
    sheet = Image.new('RGB', (1200, 2200), '#d5dae0')
    draw = ImageDraw.Draw(sheet)
    for i, path in enumerate(pages[base:base+20]):
        x, y = (i % 4) * 300, (i // 4) * 440
        im = Image.open(path).convert('RGB')
        thumb = ImageOps.contain(im, (286, 404))
        sheet.paste(thumb, (x+(300-thumb.width)//2, y+28))
        draw.text((x+10, y+5), f'Page {base+i+1}', font=font, fill='#18212d')
    out = dest / f'contact-{base+1:03}-{min(base+20,len(pages)):03}.jpg'
    sheet.save(out, quality=91)
    print(out)

info = json.loads((tmp/'validation.json').read_text(encoding='utf-8'))
for row in info['page_info']:
    if row['image_objects'] > 0:
        print('IMAGE PAGE', row['page'], row['image_objects'], row['first_text'].split('\n')[-1][:130])
