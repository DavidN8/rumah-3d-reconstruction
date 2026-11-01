"""Wait for root's completed GPU export, then CPU-filter and compare it once."""
import json
from pathlib import Path
import subprocess
import sys
import time

HERE=Path(__file__).resolve().parent
RUN=Path(r'C:\Users\bombe\OneDrive\Documents\ChatGPT\Ruang Kamare\roomscan-reconstruction\data\20261031_OSMO360\recovery-v2')
RECORD=HERE/'qa-v4-texture-pipeline.json'
LOG=HERE/'qa-v4-texture-pipeline.log'

def save(record):
    temp=RECORD.with_suffix('.tmp');temp.write_text(json.dumps(record,indent=2));temp.replace(RECORD)

def main():
    if RECORD.exists() or LOG.exists():raise RuntimeError('CPU pipeline already started; inspect the recorded attempt.')
    record={'status':'waiting_for_native_texture_export','started_unix':time.time(), 'native_record':str(RUN/'analysis/v4-texture.json'),'gpu_jobs_launched':False,'commands':[]}
    save(record);print(json.dumps(record),flush=True)
    deadline=time.monotonic()+600
    while True:
        native=json.loads((RUN/'analysis/v4-texture.json').read_text())
        if native['status']=='complete':
            if native.get('exit_code')!=0:raise RuntimeError('Native texture export failed')
            break
        if native['status']=='failed':raise RuntimeError('Native texture export failed')
        if time.monotonic()>deadline:raise TimeoutError('Native export did not finish within10min; no GPU operation retried.')
        time.sleep(2)
    filtered=RUN/'exports/v4-supported-05cm.glb'
    qa=HERE/'qa-v4-supported-05cm.json'
    commands=[
        [sys.executable,'-B',str(HERE/'qa-support-filter.py'),'--input',str(RUN/'exports/v4-texture.glb'),'--baseline',str(RUN/'exports/v4-probe.glb'),'--prefix',str(RUN/'exports/v4-supported'),'--thresholds','.05'],
        [sys.executable,'-B',str(HERE/'qa-geometry.py'),'--mesh',str(filtered),'--label','v4-supported-05cm','--out',str(qa)],
        [sys.executable,'-B',str(HERE/'qa-paired-comparison.py'),'--reference',str(HERE/'qa-baseline-trusted-v3.json'),'--candidate',str(qa),'--out',str(HERE/'qa-baseline-v4-supported-paired.json')],
        [sys.executable,'-B',str(HERE/'qa-paired-comparison.py'),'--reference',str(HERE/'qa-v4-probe.json'),'--candidate',str(qa),'--out',str(HERE/'qa-v4probe-supported-paired.json')],
    ]
    record.update(status='running_cpu_filter_and_qa',native_complete_unix=time.time());save(record)
    with LOG.open('xb',buffering=0) as log:
        for command in commands:
            step={'command':command,'started_unix':time.time()};record['commands'].append(step);save(record)
            process=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT);step['pid']=process.pid;save(record)
            code=process.wait();step.update(exit_code=code,elapsed_seconds=time.time()-step['started_unix']);save(record)
            if code:raise RuntimeError(f'CPU helper failed with exit{code}; inspect {LOG}')
    metrics=json.loads(qa.read_text());pairs=json.loads((HERE/'qa-v4probe-supported-paired.json').read_text());basepairs=json.loads((HERE/'qa-baseline-v4-supported-paired.json').read_text())
    record.update(status='complete',elapsed_seconds=time.time()-record['started_unix'],filtered_model=str(filtered),topology=metrics['topology'],visibility={k:v for k,v in metrics['visibility'].items() if k!='per_image'},vs_probe={k:v for k,v in pairs.items() if k!='per_changed_image'},vs_original={k:v for k,v in basepairs.items() if k!='per_changed_image'})
    save(record);print(json.dumps(record,indent=2),flush=True)

if __name__=='__main__':
    try:main()
    except Exception as exc:
        if RECORD.exists():
            record=json.loads(RECORD.read_text());record.update(status='failed',error=repr(exc));save(record)
        raise
