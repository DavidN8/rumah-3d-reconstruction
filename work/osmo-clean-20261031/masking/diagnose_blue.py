from pathlib import Path
from PIL import Image
import numpy as np,json
b=Path(__file__).resolve().parent.parent
yy,xx=np.mgrid[:640,:640]
roi=(xx>460)&(((xx-320)**2+(yy-320)**2)<(640*.48)**2)
rs=json.loads((b/'frame-selection.json').read_text())['selected']
want=[1374,1377,1473,1482,1485,1491,1584,1626,1629,1668,1695,1704,1737,1755,1815,1950]
out=[]
for r in rs:
    if r['source_frame'] not in want:continue
    im=np.asarray(Image.open(b/'thumbnails/cam0'/f"sample_{r['source_frame']//3+1:06d}.jpg")).astype(float)
    blue=(im[:,:,2]>im[:,:,0]*1.25)&(im[:,:,2]>im[:,:,1]*1.07)&roi
    row={'n':r['source_frame'],'blue_pixels':int(blue.sum())};name=Path(r['filename']).with_suffix('.png')
    for layer in ['narrow/operator-raw','clothing/operator-raw','operator-reviewed','candidate-final']:
        p=b/'masking'/layer/'cam0'/name
        if p.exists():
            m=np.asarray(Image.open(p).resize((640,640)))
            row[layer]=int(((m<128)&blue).sum())
    out.append(row)
print(json.dumps(out,indent=2))
