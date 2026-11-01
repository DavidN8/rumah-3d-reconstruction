"""Plot the two component-native meshes and all source poses without changing them."""
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from reconstruction_frame import read_glb,accessor,BASE
RUN=BASE/'recovery-v2'
rows=json.loads((RUN/'analysis/all-source-poses.json').read_text(encoding='utf-8'))
fig,ax=plt.subplots(1,2,figsize=(15,6.1));colors=['#d39631','#258a98'];stats=[]
for z,name in enumerate(['zone-kitchen','zone-living-bedroom-allviews']):
    d,b=read_glb(RUN/f'exports/{name}/{name}.glb');p=d['meshes'][0]['primitives'][0];xyz=accessor(d,b,p['attributes']['POSITION']);indices=accessor(d,b,p['indices'])
    rng=np.random.default_rng(876+z);s=xyz[rng.choice(len(xyz),min(150000,len(xyz)),replace=False)]
    cameras=np.array([r['position'] for r in rows if r['component']==z]);label='Kitchen' if z==0 else 'Living + corridor + bedroom'
    ax[0].scatter(s[:,0],s[:,2],s=.16,color=colors[z],alpha=.16,rasterized=True);ax[0].plot(cameras[:,0],cameras[:,2],'.',ms=2,color=colors[z],label=label)
    ax[1].scatter(s[:,2],s[:,1],s=.16,color=colors[z],alpha=.16,rasterized=True);ax[1].plot(cameras[:,2],cameras[:,1],'.',ms=2,color=colors[z])
    stats.append({'component':label,'triangles':indices.size//3,'bounds':[xyz.min(0).tolist(),xyz.max(0).tolist()],'camera_count':len(cameras),'camera_y_median':float(np.median(cameras[:,1]))})
ax[0].set(title='Top-down floorplan and source-camera positions',xlabel='X (approximate metres)',ylabel='Z (approximate metres)');ax[0].axis('equal');ax[0].legend(loc='upper right')
ax[1].set(title='Side elevation: Y is up; shared living/bedroom transform',xlabel='Z (approximate metres)',ylabel='Y (approximate metres)');ax[1].axhline(0,color='#263f52',lw=1,label='Floor datum');ax[1].axhline(1.5,color='#7d8990',ls='--',lw=.8,label='Dollhouse clipping height');ax[1].legend(loc='upper right');ax[1].set_aspect('equal',adjustable='box')
for a in ax:a.grid(alpha=.15)
fig.suptitle('Component-aligned reconstruction - no local bedroom tilt; no surveyed dimensional accuracy',fontsize=13);fig.tight_layout()
fig.savefig(RUN/'analysis/allviews-elevation-and-floorplan.png',dpi=180);plt.close(fig)
(RUN/'analysis/allviews-geometry-plot.json').write_text(json.dumps({'components':stats,'limitation':'Native mesh vertices and all source camera poses plotted in their common approximate metric frame. Not a global floor-flatness certificate.'},indent=2),encoding='utf-8');print(json.dumps(stats))
