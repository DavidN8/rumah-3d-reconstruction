"""Run one explicit argv job, recording its exact command, PID, log and result."""
from pathlib import Path
import json,os,subprocess,sys,time
job_path=Path(sys.argv[1]).resolve();job=json.loads(job_path.read_text());command=job['command'];status_path=Path(job['status']);log_path=Path(job['log'])
if status_path.exists() or log_path.exists():raise FileExistsError('Job status/log already exists; use a separately named reviewed attempt')
if not isinstance(command,list) or not command or not Path(command[0]).is_file():raise ValueError('Expected an explicit executable argv list')
status_path.parent.mkdir(parents=True,exist_ok=True);log_path.parent.mkdir(parents=True,exist_ok=True)
state={'job':str(job_path),'stage':job['stage'],'status':'starting','started_unix':time.time(),'command':command,'log':str(log_path),'runner_pid':os.getpid(),'provenance':job.get('provenance',{})}
def save():
    temporary=status_path.with_suffix('.json.partial');temporary.write_text(json.dumps(state,indent=2));temporary.replace(status_path)
save()
with log_path.open('w',encoding='utf-8') as log:
    child=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,cwd=job.get('cwd'))
    state.update(status='running',pid=child.pid);save();code=child.wait()
state.update(status='finished' if code==0 else 'failed',exit_code=code,finished_unix=time.time(),elapsed_seconds=time.time()-state['started_unix']);save()
print(json.dumps({k:v for k,v in state.items() if k not in ['command','provenance']},indent=2),flush=True);sys.exit(code)
