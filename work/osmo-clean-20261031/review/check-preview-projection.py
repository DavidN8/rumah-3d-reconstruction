"""CPU-only diagnostic: project seed and intermediate Gaussian centres at fresh poses.

This is not a Gaussian renderer or quality metric. It checks coordinate alignment
without competing for the training GPU or changing any reconstruction files.
"""
from pathlib import Path
import json,sys
import numpy as np
from scipy.spatial.transform import Rotation
from PIL import Image,ImageDraw
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent.parent/'osmo-reconstruct-20261031'))
from seed_fisheye import read_model
DATA=Path('C:/Users/bombe/OneDrive/Documents/ChatGPT/Ruang Kamare/roomscan-reconstruction/data/20261031_OSMO360/clean-v3/dataset')
_,_,points=read_model(DATA/'sparse/0')
seed_xyz=np.array([p['xyz'] for p in points.values()]);seed_rgb=np.array([p['rgb'] for p in points.values()],dtype=np.uint8)
with (HERE/'checkpoints/step-5000.ply').open('rb') as f:
    header=[]
    while (line:=f.readline())!=b'end_header\n':
        if not line:raise ValueError('Missing PLY header')
        header.append(line.decode().strip())
    props=[line.split() for line in header if line.startswith('property ')]
    types={'float':'<f4','float32':'<f4','uchar':'u1'}
    dtype=np.dtype([(p[2],types[p[1]]) for p in props])
    n=int(next(line.split()[-1] for line in header if line.startswith('element vertex ')))
    data=np.fromfile(f,dtype=dtype,count=n)
xyz=np.column_stack([data[k] for k in ['x','y','z']]);rgb=np.clip((np.column_stack([data['f_dc_'+str(i)] for i in range(3)])*.28209479177387814+.5)*255,0,255).astype(np.uint8)
canvas=Image.new('RGB',(1800,650*3),'#192028');draw=ImageDraw.Draw(canvas);poses=json.loads((HERE/'clean-cameras.json').read_text())['presets'];rows=[]
for row,index in enumerate([0,2,5]):
    pose=poses[index];source=Image.open(pose['sourceFile']).convert('RGB').resize((600,600));canvas.paste(source,(0,row*650+40));draw.text((8,row*650+10),pose['label'],fill='white')
    stats=[]
    for column,(label,positions,colors) in enumerate([('Fresh sparse seed',seed_xyz,seed_rgb),('5k Gaussian centres (no footprint)',xyz,rgb)],start=1):
        local=(positions-np.array(pose['position']))@Rotation.from_quat(pose['quaternion']).as_matrix()
        z=-local[:,2];u=300*local[:,0]/np.maximum(z,1e-9)+300;v=300-300*local[:,1]/np.maximum(z,1e-9)
        ok=(z>.02)&(u>=0)&(u<600)&(v>=0)&(v<600)
        ix=np.flatnonzero(ok);order=ix[np.argsort(z[ix])[::-1]]
        image=np.zeros((600,600,3),dtype=np.uint8);image[v[order].astype(int),u[order].astype(int)]=colors[order]
        canvas.paste(Image.fromarray(image),(column*600,row*650+40));draw.text((column*600+8,row*650+10),label,fill='white')
        stats.append({'kind':label,'visibleCentres':int(ok.sum()),'medianVisibleDepth':float(np.median(z[ok]))})
    rows.append({'pose':pose['name'],'statistics':stats})
canvas.save(HERE/'preview-projection-diagnostic.jpg',quality=94)
(HERE/'preview-projection-diagnostic.json').write_text(json.dumps({'purpose':__doc__,'rows':rows},indent=2))
print(json.dumps(rows,indent=2))
