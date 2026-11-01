from pathlib import Path
import numpy as np,json
W=Path(__file__).resolve().parent;p=W/'clean-mesh_vertexcolor.ply'
with p.open('rb') as f:
    header=b''
    while not header.endswith(b'end_header\n'):header+=f.readline()
    lines=header.decode().splitlines();nv=int(next(x.split()[-1] for x in lines if x.startswith('element vertex ')));nf=int(next(x.split()[-1] for x in lines if x.startswith('element face ')))
    v=np.fromfile(f,dtype=np.dtype([(n,'<f4') for n in ['x','y','z','nx','ny','nz']]+[(n,'u1') for n in ['red','green','blue']]),count=nv)
    faces=np.fromfile(f,dtype=np.dtype([('n','u1'),('indices','<i4',(3,))]),count=nf)
    if not np.all(faces['n']==3):raise ValueError('Non-triangle mesh')
np.stack([v[n] for n in ['x','y','z']],axis=1).astype('<f4').tofile(W/'position.bin')
np.stack([v[n] for n in ['nx','ny','nz']],axis=1).astype('<f4').tofile(W/'normal.bin')
np.stack([v[n] for n in ['red','green','blue']],axis=1).astype('u1').tofile(W/'color.bin')
faces['indices'].astype('<u4').tofile(W/'indices.bin')
print(json.dumps({'vertices':nv,'triangles':nf}))
