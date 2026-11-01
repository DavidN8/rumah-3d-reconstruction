"""Scoped OpenSSH/SFTP helper. Never kills another task's connections."""
import argparse,sys,subprocess
from pathlib import Path
import json, os

def _access_settings():
    # Source contains no workstation host, key path or access credential.
    root = Path(__file__).resolve().parents[2]
    location = Path(os.environ.get('RUMAH_SSH_CONFIG', root / '.local' / 'hosting-access.json'))
    settings = json.loads(location.read_text(encoding='utf-8')) if location.is_file() else {}
    host = os.environ.get('RUMAH_SSH_HOST') or settings.get('host')
    options = settings.get('options', ['-o', 'BatchMode=yes'])
    if not isinstance(host, str) or not host or host.startswith('-'):
        raise ValueError('Set RUMAH_SSH_HOST or configure local SSH access before remote operations.')
    if not isinstance(options, list) or not all(isinstance(value, str) for value in options):
        raise ValueError('Local SSH options must be a list of strings.')
    return host, options

def run(command,data=None,limit=45):
    HOST, OPTIONS = _access_settings()
    result=subprocess.run(['ssh','-T',*OPTIONS,HOST,command],input=data,capture_output=True,timeout=limit)
    sys.stdout.buffer.write(result.stdout);sys.stderr.buffer.write(result.stderr);return result.returncode

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--script');p.add_argument('--command');p.add_argument('--put',nargs=2);p.add_argument('--limit',type=int,default=45);a=p.parse_args()
    if a.put:
        local,remote=a.put
        if not remote.startswith('/var/lib/vz/rumah-deploy/'):raise ValueError('Task uploads must stay in the task staging directory')
        local=str(Path(local).resolve()).replace('\\','/')
        batch=Path(__file__).parent/'upload.sftp';batch.write_text(f'put -a "{local}" "{remote}"\n',encoding='utf-8')
        r=subprocess.run(['sftp','-q',*OPTIONS,'-b',str(batch),HOST],capture_output=True,timeout=a.limit)
        sys.stdout.buffer.write(r.stdout);sys.stderr.buffer.write(r.stderr);raise SystemExit(r.returncode)
    data=Path(a.script).read_bytes().replace(b'\r\n',b'\n') if a.script else None
    raise SystemExit(run('timeout -s TERM 35 bash -s' if a.script else a.command,data,a.limit))
