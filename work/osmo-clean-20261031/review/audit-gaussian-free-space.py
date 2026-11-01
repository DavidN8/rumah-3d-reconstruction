"""Read-only diagnostic for Gaussian cores intruding into known training cameras.

Camera origins supply independent empty-space evidence, not a holed mesh probe.
The diagnostic never edits/culls the model. Ellipsoid density is a proxy, not a
physically calibrated opacity/occupancy measurement or a release-quality score.
"""
from pathlib import Path
import argparse,json
import numpy as np
from scipy.spatial import cKDTree
from scipy.spatial.transform import Rotation
HERE=Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
with args.source.open('rb') as f:
    header=[]
    while (line:=f.readline())!=b'end_header\n':
        if not line:raise ValueError('Invalid PLY')
        header.append(line.decode().strip())
    offset=f.tell()
types={'float':'<f4','float32':'<f4','uchar':'u1'}
props=[line.split() for line in header if line.startswith('property ')]
dtype=np.dtype([(row[2],types[row[1]]) for row in props]);count=int(next(line.split()[-1] for line in header if line.startswith('element vertex ')))
data=np.memmap(args.source,mode='r',dtype=dtype,offset=offset,shape=(count,))
xyz=np.column_stack([data[k] for k in ['x','y','z']]);scales=np.exp(np.clip(np.column_stack([data['scale_'+str(i)] for i in range(3)]),-30,30));opacity=1/(1+np.exp(-np.clip(data['opacity'],-80,80)))
records=json.loads((HERE/'clean-cameras-registered-poses.json').read_text())['poses'];records=[r for r in records if r['split']=='train'];camera_xyz=np.array([r['position'] for r in records]);tree=cKDTree(camera_xyz)
eligible=np.flatnonzero((opacity>.1)&(scales.max(axis=1)>.05));rows=[];candidate_ids=[]
for start in range(0,len(eligible),100000):
    ids=eligible[start:start+100000];_,neighbours=tree.query(xyz[ids],k=12,workers=2)
    quaternions=np.column_stack([data['rot_'+str(i)][ids] for i in [1,2,3,0]])
    axes=Rotation.from_quat(quaternions).as_matrix()
    delta=camera_xyz[neighbours]-xyz[ids,None,:]
    local=np.einsum('nki,nij->nkj',delta,axes)/np.maximum(scales[ids,None,:],1e-12)
    d2=np.sum(local*local,axis=2);density=opacity[ids,None]*np.exp(-.5*d2)
    for j in np.flatnonzero((density>.1).sum(axis=1)>=2):
        witnesses=np.flatnonzero(density[j]>.1);frames={records[int(neighbours[j,k])]['sourceFrame'] for k in witnesses}
        if len(frames)<2:continue
        index=int(ids[j]);candidate_ids.append(index)
        order=sorted(witnesses,key=lambda k:float(density[j,k]),reverse=True)
        rows.append({'index':index,'position':xyz[index].tolist(),'scales':scales[index].tolist(),'opacity':float(opacity[index]),'maxCoreDensity':float(density[j].max()),'distinctTimestampWitnessesAmong12NearestCameras':len(frames),'witnesses':[{'name':records[int(neighbours[j,k])]['name'],'sourceTimeSeconds':records[int(neighbours[j,k])]['sourceTimeSeconds'],'densityProxy':float(density[j,k])} for k in order[:4]]})
rows.sort(key=lambda r:r['maxCoreDensity'],reverse=True)
report={'purpose':__doc__,'source':str(args.source.resolve()),'sourceSplats':count,'trainingCameras':len(records),'screenedSplats':len(eligible),'coreIntrusionCandidates':len(candidate_ids),'units':'Fresh normalized arbitrary units, not metres','scaleMaxPercentiles':{str(q):float(np.percentile(scales.max(axis=1),q)) for q in [50,90,99,99.9,100]},'examples':rows[:100],'modifiedModel':False,'caveat':'Nearest-12-camera screening can miss a more distant camera. Gaussian tails alone are not evidence of a bad splat. No spatial or photometric culling is performed.'}
args.output.write_text(json.dumps(report,indent=2));np.save(args.output.with_suffix('.indices.npy'),np.asarray(candidate_ids,np.int64));print(json.dumps({k:v for k,v in report.items() if k not in ['purpose','examples']},indent=2))
