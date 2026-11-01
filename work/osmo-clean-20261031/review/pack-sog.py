"""Reproducible official SOG packing with an explicit Mip tag; CPU by default."""
from pathlib import Path
import argparse, hashlib, json, subprocess, time, zipfile
HERE=Path(__file__).resolve().parent
parser=argparse.ArgumentParser();parser.add_argument('--source',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--gpu',default='cpu');parser.add_argument('--gpu-backend',choices=['vulkan','d3d12','metal']);args=parser.parse_args()
source=args.source.resolve();output=args.output.resolve();tool=HERE/'converter/node_modules/@playcanvas/splat-transform/bin/cli.mjs'
if output.exists():raise FileExistsError(output)
scratch=HERE/(output.stem+'.mip-tagged-input.ply')
if scratch.exists():raise FileExistsError(scratch)
start=time.monotonic()
source_hash=hashlib.sha256()
# Spirula's PLY lacks its config's primitive tag. Add only a standard metadata
# comment to a temporary copy; preserve every binary Gaussian attribute byte.
with source.open('rb') as f:
    header=b''
    while not header.endswith(b'end_header\n'):
        line=f.readline();header+=line
        if not line or len(header)>100000:raise ValueError('Invalid PLY header')
    if b'format binary_little_endian 1.0' not in header:raise ValueError('Expected binary little-endian PLY')
    if b'SplatRenderMode:' in header and b'SplatRenderMode: mip' not in header:raise ValueError('Source declares a different primitive; do not override it')
    properties=[line.split()[-1] for line in header.decode().splitlines() if line.startswith('property ')]
    rest=[name for name in properties if name.startswith('f_rest_')]
    degree_by_rest_count={0:0,9:1,24:2,45:3}
    if len(rest) not in degree_by_rest_count or set(rest)!={f'f_rest_{i}' for i in range(len(rest))}:raise ValueError('Unexpected SH coefficient layout')
    source_degree=degree_by_rest_count[len(rest)]
    tagged=header.replace(b'end_header\n',b'comment SplatRenderMode: mip\nend_header\n')
    source_hash.update(header)
    with scratch.open('xb') as dst:
        dst.write(tagged)
        while chunk:=f.read(1024*1024):source_hash.update(chunk);dst.write(chunk)
command=['node',str(tool),'-g',args.gpu,'--max-workers','2']
if args.gpu_backend:command+=['--gpu-backend',args.gpu_backend]
command += [str(scratch),str(output)]
log=output.with_suffix('.sog.log')
with log.open('w',encoding='utf-8') as f:result=subprocess.run(command,stdout=f,stderr=subprocess.STDOUT,cwd=HERE)
if result.returncode:raise RuntimeError(f'Converter exit {result.returncode}; inspect {log}')
with zipfile.ZipFile(output) as z:meta=json.loads(z.read('meta.json'));members=[{'name':x.filename,'bytes':x.file_size} for x in z.infolist()]
count=int(next(x.split()[-1] for x in header.decode().splitlines() if x.startswith('element vertex ')))
if meta['count']!=count or meta.get('model')!='antialiased':raise AssertionError('Count/antialias tag changed')
output_degree=meta.get('shN',{}).get('bands',0)
if output_degree!=source_degree:raise AssertionError('SH degree changed')
with output.open('rb') as f:digest=hashlib.file_digest(f,'sha256').hexdigest()
report={'source':str(source),'output':str(output),'sourceSha256':source_hash.hexdigest(),'sourceBytes':source.stat().st_size,'bytes':output.stat().st_size,'sha256':digest,'splats':count,'shDegree':output_degree,'sourceShDegree':source_degree,'model':meta.get('model'),'sourceCountPreserved':True,'sourceShDegreePreserved':True,'under50MB':output.stat().st_size<=50000000,'format':'sog','tool':'@playcanvas/splat-transform 3.10.3','command':command,'primitiveDeclaration':'Mip supplied by wrapper, consistent with the audited old v4 and planned fresh mip training. Verify training config before using on another scene.','sourceModification':'Temporary header-only Mip comment added; all binary splat bytes unchanged. Original file unmodified.','members':members,'seconds':time.monotonic()-start,'validation':'Count/SH-degree/model metadata only. Visual fidelity must be checked separately against original Gaussian renders; not a phone loading benchmark.'}
output.with_suffix('.sog.json').write_text(json.dumps(report,indent=2))
# This exact disposable copy was created above, exclusively inside this review.
assert scratch.parent==HERE and scratch.name==output.stem+'.mip-tagged-input.ply';scratch.unlink()
print(json.dumps({k:v for k,v in report.items() if k!='members'},indent=2))
