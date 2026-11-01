"""Plan or apply narrow generated-file cleanup with per-file provenance checks.

No recursive delete. All targets resolve inside the workspace. Original footage,
models, source, masks, calibration, gate records and reports are kept. One proven
duplicate model download can be removed while all canonical aliases remain.
"""
from pathlib import Path
from collections import Counter,defaultdict
import argparse,hashlib,json,os,re,time
import repo_audit as audit
ROOT=audit.ROOT;OUT=audit.AUDIT

def sha(p):return audit.digest(p)[0]

def make_plan():
    inv=json.loads((OUT/'inventory-before.json').read_text());rows=inv['files'];targets=[]
    source_reports=[ROOT/'outputs/Osmo_Video_to_Mesh_Processing_Audit_2026-10-31.pdf',ROOT/'output/pdf/Osmo_Quality_Controls_and_Pipeline_Review_2026-10-31.pdf']
    reports_present=all(p.is_file() and p.stat().st_size>1000000 for p in source_reports)
    for r in rows:
        rel=r['path'];reason=None;restore=None
        if r['role']=='CACHE':reason='Regenerable Python bytecode; authored source retained.';restore='Python regenerates on next import.'
        elif r['role']=='FIXTURE':reason='Old synthetic deployment-test sandbox.';restore='The corresponding audit_deploy_helper.py test recreates fixtures.'
        elif reports_present and rel.startswith('tmp/pdfs/') and re.search(r'/(?:render[^/]*|pages[^/]*)/page-\d+\.png$',rel):reason='Rendered page of a retained finalized PDF.';restore='Render the corresponding retained PDF with pdftoppm.'
        elif reports_present and rel.startswith('tmp/pdfs/') and ('/contact-sheets' in rel or re.search(r'/contact-\d+\.jpg$',rel)):reason='Temporary montage of retained PDF page renders.';restore='Render retained PDF and regenerate contact sheets.'
        elif r['role']=='BUFFER':
            parent=(ROOT/rel).parent
            if parent.name=='mesh-pilot' and (parent/'clean-mesh_vertexcolor.ply').is_file() and (parent/'unpack-vertex.py').is_file():reason='Typed packing buffer derived from retained full-precision PLY.';restore='Run review/mesh-pilot/unpack-vertex.py before pack-vertex.mjs.'
            elif parent.name=='poisson-pilot' and all((parent/f).is_file() for f in ['surface-carved.npz','surface-compact.npz']):reason='Typed packing buffer; both source and compact NPZ geometry retained.';restore='Re-export arrays from retained NPZ; poisson-preview.py / simplify-poisson.mjs record the original derivation.'
        elif rel.startswith('work/osmo-clean-20261031/review/.clean-preview15-gpu.sog.') and rel.endswith('.tmp'):reason='Abandoned temporary packing output; final models retained.';restore='Rerun the recorded pack command if this old trial is needed.'
        if reason:
            p=ROOT/rel
            if not p.resolve().is_relative_to(ROOT) or p.is_symlink():continue
            targets.append({**r,'reason':reason,'regeneration':restore,'sha256':sha(p)})
    duplicate=ROOT/'work/hosting/public-model-verified.glb';canonical=ROOT/'outputs/iPhone_Wide_Full_Native.glb'
    if duplicate.is_file() and canonical.is_file() and sha(duplicate)==sha(canonical)=='16f8963b043a766317497ee4281f4cf39c6b2190fafaaed51334734723c8b207':
        row=next(r for r in rows if r['path']=='work/hosting/public-model-verified.glb');targets.append({**row,'sha256':sha(duplicate),'reason':'Byte-identical downloaded verification copy; canonical iPhone Full and its hardlinked aliases remain.','regeneration':'Copy the retained canonical iPhone Full model.','retainedCanonical':str(canonical),'canonicalSha256':sha(canonical)})
    grouped=defaultdict(list)
    for r in targets:grouped[(r['device'],r['file_id'])].append(r)
    estimated=sum(rs[0]['bytes'] for rs in grouped.values() if len(rs)==rs[0]['links'])
    plan={'workspace':str(ROOT),'policy':'No recursive deletion; only named, hashed regenerable files and one proven duplicate download. No original or unique model, source video, source mask/calibration, report or acceptance evidence is deleted.','targets':targets,'files':len(targets),'logicalBytes':sum(x['bytes'] for x in targets),'estimatedUniqueBytesReleased':estimated,'reasons':dict(Counter(x['reason'] for x in targets)),'externalFilesDeleted':0,'modelsAndVideoKept':True}
    (OUT/'cleanup-plan.json').write_text(json.dumps(plan,indent=2));print(json.dumps({k:v for k,v in plan.items() if k!='targets'},indent=2))

def apply():
    plan=json.loads((OUT/'cleanup-plan.json').read_text());journal=OUT/'cleanup-journal.jsonl'
    if journal.exists():raise FileExistsError('Inspect existing cleanup journal before repeating')
    free_before=__import__('shutil').disk_usage(ROOT).free;deleted=[]
    with journal.open('a',encoding='utf-8') as log:
        for row in plan['targets']:
            p=ROOT/row['path'];resolved=p.resolve(strict=True)
            if not resolved.is_relative_to(ROOT) or p.is_symlink() or not p.is_file():raise ValueError('Target escaped workspace or changed kind: '+row['path'])
            s=p.stat()
            if s.st_size!=row['bytes'] or str(s.st_ino)!=row['file_id'] or sha(p)!=row['sha256']:raise ValueError('Target changed since review: '+row['path'])
            if row.get('retainedCanonical') and sha(Path(row['retainedCanonical']))!=row['canonicalSha256']:raise ValueError('Canonical duplicate source changed')
            p.unlink();deleted.append(row);log.write(json.dumps({**row,'actionTaken':'deleted_exact_file'})+'\n');log.flush()
    # All surviving authored code/test bytes from the before snapshot must match.
    baseline=json.loads((OUT/'inventory-before.json').read_text());protected=[r for r in baseline['files'] if r['role'] in {'CORE','TEST'} and r.get('sha256')]
    for r in protected:
        if not (ROOT/r['path']).is_file() or sha(ROOT/r['path'])!=r['sha256']:raise AssertionError('Authored source changed during cleanup: '+r['path'])
    report={'filesDeleted':len(deleted),'logicalBytesRemoved':sum(r['bytes'] for r in deleted),'estimatedUniqueBytesReleased':plan['estimatedUniqueBytesReleased'],'volumeFreeBefore':free_before,'volumeFreeAfter':__import__('shutil').disk_usage(ROOT).free,'volumeDeltaCaveat':'Other applications may change free space; linked files may remain allocated through external paths.','authoredCodeFilesVerifiedUnchanged':len(protected),'uniqueModelsRemoved':0,'sourceVideosRemoved':0,'externalFilesRemoved':0,'reportFilesRemoved':0,'recursiveDeleteUsed':False,'journal':str(journal)}
    (OUT/'cleanup-result.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--apply',action='store_true');a=p.parse_args();apply() if a.apply else make_plan()
