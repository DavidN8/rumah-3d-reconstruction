from pathlib import Path
import struct,json,io
import numpy as np
from PIL import Image
H=Path(__file__).parent
P=Path(r'C:\Users\bombe\OneDrive\Documents\ChatGPT\Ruang Kamare\roomscan-reconstruction\data\20261031_OSMO360\lite-v1')
paths={'osmo_source':P/'exports/osmo-lite-source.glb','osmo_lite':P/'exports/osmo-lite.glb',
       'iphone':H.parents[1]/'outputs/iPhone_Wide_Full_Native.glb'}
report={}
for label,path in paths.items():
    with path.open('rb') as f:
        magic,v,length=struct.unpack('<III',f.read(12));size,kind=struct.unpack('<II',f.read(8));g=json.loads(f.read(size));binsize,binkind=struct.unpack('<II',f.read(8));binoff=f.tell()
        r={'path':str(path),'materials':g.get('materials'),'extensionsUsed':g.get('extensionsUsed'),'primitives':[p for m in g['meshes'] for p in m['primitives']],'images':[]}
        for i,img in enumerate(g.get('images',[])):
            if 'bufferView' not in img:continue
            view=g['bufferViews'][img['bufferView']];f.seek(binoff+view.get('byteOffset',0));raw=f.read(view['byteLength'])
            image=Image.open(io.BytesIO(raw)).convert('RGB');x=np.asarray(image);lum=x@np.array([.2126,.7152,.0722]);nonblack=lum>8
            r['images'].append({'size':image.size,'format':img.get('mimeType'),'mean_rgb':x.mean((0,1)).tolist(),'mean_nonblack_rgb':x[nonblack].mean(0).tolist(),'nonblack_fraction':float(nonblack.mean()),'luminance_percentiles':np.percentile(lum,[1,10,25,50,75,90,99]).tolist()})
            if label=='osmo_source':image.resize((1024,1024)).save(H/f'{label}-atlas-{i}.jpg')
    report[label]=r
for label,file,mask in [('source_frame',P/'dataset/images/cam0/frame_000003.jpg',P/'dataset/masks/cam0/frame_000003.jpg.png')]:
    x=np.array(Image.open(file).convert('RGB'));lum=x@np.array([.2126,.7152,.0722]);nonblack=lum>8
    report[label]={'mean_rgb':x[nonblack].mean(0).tolist(),'nonblack_fraction':float(nonblack.mean()),'luminance_percentiles':np.percentile(lum[nonblack],[1,10,25,50,75,90,99]).tolist()}
(H/'color-inspection.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
