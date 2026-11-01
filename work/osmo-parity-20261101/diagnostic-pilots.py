"""Small tests of the remaining blur hypotheses, never automatic full reruns."""
from pathlib import Path
import json,subprocess,sys
W=Path(__file__).resolve().parent;template=json.loads(Path('C:/Users/bombe/OneDrive/Documents/ChatGPT/Ruang Kamare/roomscan-reconstruction/data/20261031_OSMO360/parity-20261101/pilots/sharp-1600/request.json').read_text());ROOT=Path(template['status']).parent.parent/'diagnostics'
cases=[('rgb-only-mip',{'--load-depths':0,'--load-normals':0,'--depth-supervision-weight':0,'--normal-supervision-weight':0,'--normal-reg-weight':0,'--depth-distortion-reg':0,'--normal-distortion-reg':0}),('rgb-only-3dgs',{'--primitive':'3dgs','--load-depths':0,'--load-normals':0,'--depth-supervision-weight':0,'--normal-supervision-weight':0,'--normal-reg-weight':0,'--depth-distortion-reg':0,'--normal-distortion-reg':0}),('no-appearance-correction',{'--use-ppisp':0,'--use-bilateral-grid':0})]
for name,changes in cases:
    root=ROOT/name;root.mkdir(parents=True,exist_ok=True);command=template['command'][:]
    changes.update({'--output-dir-prefix':root/'training','--output-dir-name':name})
    for flag,value in changes.items():
        if flag in command:command[command.index(flag)+1]=str(value)
        else:command.extend([flag,str(value)])
    request=root/'request.json';status=root/'job.json'
    if status.exists():raise FileExistsError('Inspect existing diagnostic before repeating: '+str(status))
    job={'stage':name,'command':command,'cwd':str(W),'log':str(root/'train.log'),'status':str(status),'provenance':{'coldStart':True,'same1600PilotDataAndDenseSeed':True,'steps':8000,'splats':1500000,'scope':'Diagnostic only; no release or full rerun authorized by this script','changedGroup':changes}}
    request.write_text(json.dumps(job,indent=2,default=str));result=subprocess.run([sys.executable,str(W/'run_logged_job.py'),str(request)])
    if result.returncode:raise RuntimeError(name+' failed')
