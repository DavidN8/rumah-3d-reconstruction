set -eu
python3 - <<'PY'
import json,subprocess,os
def run(args):
 p=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=25)
 return {'code':p.returncode,'stdout':p.stdout[:12000],'stderr':p.stderr[:1000]}
print(json.dumps({'next_710':run(['pvesh','get','/cluster/nextid','--vmid','710']),'frufru_config':run(['pct','config','700']),'global_agent_instructions':{p:open(p).read()[:6000] for p in ['/AGENTS.md','/root/AGENTS.md'] if os.path.isfile(p)}},indent=2))
PY
pct exec 700 -- bash -c 'command -v cloudflared; cloudflared --version; systemctl is-active nginx cloudflared; find /etc/cloudflared /root/.cloudflared -maxdepth 2 -type f -printf "%p\n" 2>/dev/null || true'
pct exec 700 -- bash -c 'nginx -T 2>/dev/null' | python3 -c 'import sys,re;print("".join(l for l in sys.stdin if re.match(r"\s*(server_name|listen|root|alias|auth_basic|auth_basic_user_file|proxy_pass)\b",l)))'
pct exec 700 -- python3 - <<'PY'
from pathlib import Path
import json,re
out={}
for root in ['/etc/cloudflared','/root/.cloudflared']:
 for p in Path(root).glob('*.y*ml'):
  lines=[l for l in p.read_text().splitlines() if re.match(r'^\s*(-?\s*hostname:|service:|tunnel:|credentials-file:|origincert:)',l)]
  out[str(p)]=lines
print(json.dumps({'tunnel_config_metadata':out,'account_certificate_present':Path('/root/.cloudflared/cert.pem').is_file()},indent=2))
PY
