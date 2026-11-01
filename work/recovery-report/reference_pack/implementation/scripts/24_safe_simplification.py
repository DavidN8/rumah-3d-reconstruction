"""Bounded simplification trials with independent sampled surface checks.

Pin native geometry around any observed >2mm deviation. A failed trial is never
promoted, and the raw source is preserved. This is not a global Hausdorff proof.
"""
import argparse,json,subprocess,shutil
import numpy as np
from pathlib import Path
from importlib.machinery import SourceFileLoader
core=SourceFileLoader('recovery_core',str(Path(__file__).with_name('20_component_recovery.py'))).load_module()
BASE,RUN=core.BASE,core.RUN
NODE=Path(r'C:/Users/bombe/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe')

def protection_samples(m):
    return [v for d in ['native_to_simplified','simplified_to_native'] for p in m[d].get('bad_samples',[])
            for v in [p['point'],*p.get('source_vertices',[]),*p.get('target_vertices',[])]]

def protection_boxes(m):
    result=[]
    for direction in ['native_to_simplified','simplified_to_native']:
        for p in m[direction].get('bad_samples',[]):
            for key in ['source_vertices','target_vertices']:
                if key in p:
                    xyz=np.array(p[key]);result.append([(xyz.min(0)-.003).tolist(),(xyz.max(0)+.003).tolist()])
    return result

def main(name,target):
    src=RUN/f'exports/{name}/{name}.glb';out=RUN/f'exports/{name}/{name}-compact.glb'
    protection={};rounds=[]
    previous=RUN/f'analysis/{name}-deviation-trial-1.json'
    if previous.exists():
        rec=json.loads(previous.read_text(encoding='utf-8'))
        if rec.get('source')==str(src):
            for i,m in enumerate(rec['meshes']):
                protection[m.get('mesh',f'mesh-{i}')]={'points':protection_samples(m),'boxes':protection_boxes(m)}
    for k in range(1,5):
        pf=RUN/f'analysis/{name}-protection-{k}.json';core.save(pf,protection)
        candidate=RUN/f'exports/{name}/{name}-compact-trial-{k}.glb';report=RUN/f'analysis/{name}-deviation-trial-{k}.json'
        cmd=[str(NODE),'--max-old-space-size=8192',str(BASE/'viewer-src/simplify-recovery.mjs'),str(src),str(candidate),str(target),'0.002',str(pf)]
        with (RUN/f'logs/{name}-compact-{k}.log').open('wb') as log:r=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,cwd=BASE)
        if r.returncode:raise RuntimeError('Simplification command failed')
        cmd=[str(NODE),'--max-old-space-size=8192',str(BASE/'viewer-src/check-recovery-deviation.mjs'),str(src),str(candidate),str(report)]
        with (RUN/f'logs/{name}-deviation-{k}.log').open('wb') as log:r=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,cwd=BASE)
        if r.returncode:raise RuntimeError('Deviation measurement failed')
        measured=json.loads(report.read_text(encoding='utf-8'));simp=json.loads(Path(str(candidate)+'.json').read_text(encoding='utf-8'))
        bads=sum(len(m[d]['bad_samples']) for m in measured['meshes'] for d in ['native_to_simplified','simplified_to_native'])
        rounds.append({'trial':k,'triangles':simp['triangles'],'bytes':simp['bytes'],'sampled_gate':measured['sampled_gate'],'bad_samples':bads,'deviation_report':str(report)})
        print(json.dumps(rounds[-1]),flush=True)
        if measured['sampled_gate']:
            shutil.copy2(candidate,out);shutil.copy2(str(candidate)+'.json',str(out)+'.json');core.save(RUN/f'analysis/{name}-simplification-gate.json',{'sampled_gate':True,'output':str(out),'trials':rounds,'requires_hole_regression_gate':True});return
        for m in measured['meshes']:
            protection.setdefault(m['mesh'],{'points':[],'boxes':[]})
            protection[m['mesh']]['points']+=protection_samples(m)
            protection[m['mesh']]['boxes']+=protection_boxes(m)
    core.save(RUN/f'analysis/{name}-simplification-gate.json',{'sampled_gate':False,'trials':rounds,'next':'Retain native and do not claim 2mm delivery acceptance.'})
    raise SystemExit(2)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--zone',required=True);p.add_argument('--target',type=int,required=True);a=p.parse_args();main(a.zone,a.target)
