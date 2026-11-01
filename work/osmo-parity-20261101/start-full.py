"""One fresh 50k full rebuild after the matched pilot review; no deployment."""
from pathlib import Path
import json,subprocess,sys,hashlib
W=Path(__file__).resolve().parent;OLD=W.parent/'osmo-clean-20261031';prepared=json.loads((W/'highres-preparation.json').read_text());DS=Path(prepared['outputDataset']);ROOT=DS.parent
if not prepared['sameViewIdentity'] or prepared['sources']!=452 or prepared['train']!=2031 or prepared['eval']!=188:raise ValueError('Full input identity gate failed')
scores=json.loads((W/'review/qa/scores.json').read_text())['rows'];base={r['view']:r for r in scores if r['model']=='pilot-base'};sharp={r['view']:r for r in scores if r['model']=='pilot-sharp'}
if sum(sharp[k]['cropPSNR']>base[k]['cropPSNR'] for k in base)<3:raise ValueError('Matched pilot lacks sufficient localized gains to justify full run')
gate={'status':'approved_for_one_full_processing_run_only','basis':'Four full-viewport source-camera renders reviewed; modest local gains in fridge/fan/bathroom detail against matched 8k baseline; dining effectively unchanged. No bathroom obstruction. This is not release acceptance or a claim of a full-viewport sharpness leap.','steps':8000,'pilotSplats':1500000,'cropPSNRDelta':{k:sharp[k]['cropPSNR']-base[k]['cropPSNR'] for k in base},'sourceSeedSame':True,'fullReleaseGateStillRequired':True}
(W/'pilot-processing-gate.json').write_text(json.dumps(gate,indent=2))
command=json.loads((OLD/'explicit-full-train-job.json').read_text())['command']
def option(flag,value):
    if flag in command:command[command.index(flag)+1]=str(value)
    else:command.extend([flag,str(value)])
for flag,value in {'--data':DS,'--output-dir-prefix':ROOT/'training','--output-dir-name':'osmo-sharp-1600-full','--num-iterations':50000,'--refine-stop-iter':40000,'--refine-stop-num-iter':10000,'--seed-pointcloud':DS/'seed-dense-train.ply','--cap-max':3000000,'--means-lr':.00016,'--means-lr-final':.0000016,'--noise-lr':10,'--noise-lr-final':0,'--normal-reg-weight':.015,'--floater-suppression':'mild','--use-ppisp':1,'--use-bilateral-grid':1,'--use-bilateral-grid-for-geometry':0,'--steps-per-save':10000,'--save-full-checkpoint':1}.items():option(flag,value)
job={'stage':'full-1600-native-angular-sharpness-rebuild','command':command,'cwd':str(W),'log':str(ROOT/'full-train.log'),'status':str(ROOT/'full-train-job.json'),'provenance':{'coldStart':True,'oldGaussianInitialization':False,'sourceCamerasMasksAndTimestampSplitsPreserved':True,'seedSha256':prepared['seedSha256'],'RGBResolution':1600,'geometryResolution':768,'trainingCoordinateFrame':'unchanged audited +Y-up normalized frame','PPISPPreviouslyEnabled':True,'appearanceOnlyCorrectionNow':True,'pilotProcessingGate':str(W/'pilot-processing-gate.json'),'deploymentApproved':False}}
request=W/'full-sharp-request.json';request.write_text(json.dumps(job,indent=2));raise SystemExit(subprocess.call([sys.executable,str(W/'run_logged_job.py'),str(request)]))
