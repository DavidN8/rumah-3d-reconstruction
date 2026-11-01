from pathlib import Path
import json,hashlib,datetime
W=Path(__file__).resolve().parent;R=W/'review';P=R/'production'
def load(p):return json.loads(p.read_text())
build=load(P/'build-report.json');candidate=load(P/'candidate.json');checks=load(R/'controls-verification.json');inputs=load(W/'input-contract-verification.json');choice=load(R/'choice-and-phone-policy-verification.json');public=load(W/'production-readonly-check.json')
assert all(c['pass'] for c in checks['checks']) and not checks['errors'];assert inputs['passed'];assert all(p['preserved'] for p in inputs['iphoneModels']);assert public['previousBundleStillReferenced'] and not public['newBundleReferenced']
def evidence(names):
    rows=[]
    for name in names:
        p=W/name
        if not p.is_file():raise FileNotFoundError(p)
        rows.append({'path':str(p.resolve()),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size})
    return rows
views=['fridge','fan','dining','bathroom']
data={'dateLocal':'2026-11-01','reviewOnly':True,'approvedForDeployment':False,'releaseId':build['build'],'modelSha256':candidate['sha256'],'modelBytes':candidate['bytes'],'liveReleaseUnchanged':public['previousBuild'],'gates':{
 'dollhouse':{'status':'FAIL','behaviorPassed':True,'visualAccepted':False,'reason':'Occupied framing and FOV restored; native Gaussian outside cutaway remains spiky/untidy; no tested surface accepted as a clean full-height replacement.'},
 'navigationAndShell':{'status':'FAIL / behavior PASS','behaviorPassed':True,'visualAccepted':False,'reason':'Top, reversible shell state, interior Walk, reset and preset-exit tests pass. Clean visual shell and object preservation are not accepted.'},
 'sharpness':{'status':'FAIL','visualAccepted':False,'reason':'The actual 50k/1600 rebuild has only small mixed changes at the four fixed 1920x1080 detail views; no clear leap. Photo-textured surfaces are sharper in places but geometrically defective.'},
 'quota':{'status':'PASS','modelBytes':candidate['bytes'],'totalModelLimit':50000000,'prechoiceModelBytes':0,'iphoneHashesPreserved':True,'applicationBytesSeparately':build['metafile'] and sum(x.get('bytes',0) for x in build['metafile']['outputs'].values()),'physicalPhoneVerified':False,'reason':'Explicit chooser verified bare, deep links and selection changes; iPhone binary and metadata hashes preserved. Touch/DPR emulation is not physical phone validation.'}},
 'controlsChecks':len(checks['checks']),'sourceFilesPreserved':inputs['baselineFilesVerifiedUnchanged'],'trainingFinished':True,'gaussianRebuildPacked':True,'optionBSurfaceStatus':'See final surface audits and photographic comparisons; no promotion based only on continuity or file size.',
 'evidence':evidence(['review/evidence/01-osmo-dollhouse.png','review/evidence/02-osmo-top.png','review/evidence/03-osmo-roof-restored.png','review/controls-verification.json','review/choice-and-phone-policy-verification.json','input-contract-verification.json','production-readonly-check.json']+[f'review/qa/newest-{v}.png' for v in views]+[f'review/qa/new-full-50000-{v}.png' for v in views])}
(W/'acceptance-gates.json').write_text(json.dumps(data,indent=2))
approval=load(P/'release-approval.json');approval['approvedForDeployment']=False;approval['qualityChecks']['iphoneHashesPreserved']=True;approval['evidence']=data['evidence'];(P/'release-approval.json').write_text(json.dumps(approval,indent=2))
print(json.dumps({'approvedForDeployment':False,'gates':{k:v['status'] for k,v in data['gates'].items()},'evidenceFiles':len(data['evidence']),'physicalPhonesVerified':False},indent=2))
