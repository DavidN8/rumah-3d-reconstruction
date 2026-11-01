from pathlib import Path
import sys
import numpy as np
W=Path(__file__).resolve().parent;sys.path[:0]=[str(W.parent/'tsdfdeps'),str(W.parent)]
from scipy.spatial import cKDTree
from occupied_bounds import ply,DS
OUT=W/'poisson-pilot';data=np.load(OUT/'surface-carved.npz');v=data['positions'];cloud=ply(DS/'seed-dense-train.ply');xyz=np.stack([cloud[n] for n in ['x','y','z']],axis=1);rgb=np.stack([cloud[n] for n in ['red','green','blue']],axis=1);_,near=cKDTree(xyz).query(v,workers=12)
for name,a in [('position',v),('normal',data['normals']),('color',rgb[near].astype('u1')),('indices',data['faces'].astype('u4'))]:
    file=OUT/(name+'.bin')
    if file.exists():raise FileExistsError(file)
    a.tofile(file)
print('Prepared conservative vertex preview',len(v),'vertices')
