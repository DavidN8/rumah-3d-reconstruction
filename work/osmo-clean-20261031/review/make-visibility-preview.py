"""Create a separate experimental PLY copy for a controlled visibility comparison.

Original checkpoint is immutable. Removal candidates are supplied by the read-only
negative-ray audit. This does not approve a release or prove the candidates wrong.
"""
from pathlib import Path
import argparse,hashlib,json,re
import numpy as np
P=argparse.ArgumentParser();P.add_argument('--source',type=Path,required=True);P.add_argument('--audit',type=Path,required=True);P.add_argument('--output',type=Path,required=True);a=P.parse_args()
if a.output.exists():raise FileExistsError(a.output)
audit=json.loads(a.audit.read_text());source=a.source.resolve()
if Path(audit['source']).resolve()!=source:raise ValueError('Audit identifies a different source')
remove=np.load(a.audit.with_suffix('.indices.npy'));remove=np.unique(remove)
with source.open('rb') as f:
    header=b''
    while not header.endswith(b'end_header\n'):
        line=f.readline()
        if not line:raise ValueError('Invalid PLY')
        header+=line
    offset=f.tell()
props=[line.split() for line in header.decode().splitlines() if line.startswith('property ')]
if any(line[1]!='float' for line in props):raise ValueError('Expected float PLY attributes')
dtype=np.dtype([(line[2],'<f4') for line in props]);n=int(re.search(rb'^element vertex (\d+)$',header,re.M)[1])
if n!=audit['sourceSplats'] or len(remove)!=audit['diagnosticCandidates'] or np.any((remove<0)|(remove>=n)):raise ValueError('Audit indices/count mismatch')
keep=np.ones(n,bool);keep[remove]=False;new_n=int(keep.sum());data=np.memmap(source,mode='r',dtype=dtype,offset=offset,shape=(n,))
updated=re.sub(rb'^element vertex \d+$',b'element vertex '+str(new_n).encode(),header,count=1,flags=re.M)
with a.output.open('xb') as f:
    f.write(updated)
    for i in range(0,n,100000):f.write(data[i:i+100000][keep[i:i+100000]].tobytes())
if a.output.stat().st_size!=len(updated)+new_n*dtype.itemsize:raise ValueError('Output byte count mismatch')
def sha(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
report={'source':str(source),'sourceSha256':sha(source),'audit':str(a.audit.resolve()),'auditSha256':sha(a.audit),'indicesSha256':sha(a.audit.with_suffix('.indices.npy')),'originalCount':n,'removedForExperiment':len(remove),'outputCount':new_n,'output':str(a.output.resolve()),'outputSha256':sha(a.output),'originalCheckpointModified':False,'remainingAttributesPreservedByteForByteInOriginalOrder':True,'approvedForDeployment':False,'scope':__doc__}
a.output.with_suffix('.preview.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
