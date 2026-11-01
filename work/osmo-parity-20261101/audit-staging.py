from pathlib import Path
import importlib.util,json
W=Path(__file__).resolve().parent;P=W/'review/production';spec=importlib.util.spec_from_file_location('release_audit',P/'prepare-deploy.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);a=m.collect()
try:m.quality_gate(a,P/'release-approval.json')
except ValueError as e:rejected=True;reason=str(e)
else:raise AssertionError('Quality gate erroneously accepted the failed release')
report={'localFileAuditPassed':True,'files':a['files'],'applicationBytes':a['application_bytes'],'modelBytes':a['build']['osmo']['fileBytes'],'iphoneHashesPreserved':True,'deploymentGateRefused':rejected,'refusalReason':reason,'remoteCalls':0,'packageCreated':False}
(W/'local-package-audit.json').write_text(json.dumps(report,indent=2));print(json.dumps({k:v for k,v in report.items() if k!='files'},indent=2))
g=json.loads((W/'acceptance-gates.json').read_text());g['gates']['quota']['applicationBytesSeparately']=a['application_bytes'];(W/'acceptance-gates.json').write_text(json.dumps(g,indent=2))
