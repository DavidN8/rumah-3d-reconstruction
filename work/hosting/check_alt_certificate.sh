set -eu
pct status 710
tail -n 10 /var/lib/vz/rumah-deploy/20261027/create-container.log
pct exec 102 -- cloudflared --version
python3 - <<'PY'
import subprocess,json
p=subprocess.run(['pct','exec','102','--','cloudflared','tunnel','list','--output','json'],capture_output=True,text=True,timeout=20)
result={'certificate_probe_exit':p.returncode,'stderr':p.stderr[:1500]}
if p.returncode==0:
 result['tunnels']=[{k:x.get(k) for k in ['id','name','createdAt']} for x in json.loads(p.stdout)]
print(json.dumps(result,indent=2))
PY
