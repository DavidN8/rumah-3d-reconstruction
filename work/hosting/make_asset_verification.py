from pathlib import Path
import json
w=Path(__file__).parent
m=json.loads((w/'payload-manifest.json').read_text())
assets=[x for x in m['public_assets'] if not x['path'].endswith('.gz')]
program='''import subprocess,hashlib,json,concurrent.futures,datetime,pathlib,re
assets=ASSETS
def check(item):
    url='https://rumah.shizuku.rest/'+item['path']
    r=subprocess.run(['curl','--silent','--show-error','--fail','--compressed','--location','--proto-redir','=https','--max-time','15',url],capture_output=True,timeout=20)
    data=r.stdout
    digest=hashlib.sha256(data).hexdigest()
    canonical=data
    edge_detection=False
    if item['path']=='index.html' and b'/cdn-cgi/challenge-platform/scripts/jsd/main.js' in data:
        canonical=re.sub(rb'<script>\\(function\\(\\)\\{function c\\(\\).*?</script>',b'',data,flags=re.S)
        edge_detection=canonical!=data
    canonical_digest=hashlib.sha256(canonical).hexdigest()
    passed=r.returncode==0 and canonical_digest==item['sha256'] and len(canonical)==item['bytes']
    return dict(path=item['path'],curl_result=r.returncode,bytes=len(data),sha256=digest,origin_sha256=canonical_digest,cloudflare_detection_added=edge_detection,passed=passed,error=r.stderr.decode(errors='replace') if r.returncode else '')
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
    result=list(pool.map(check,assets))
out={'checked_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'anonymous_http_assets':result,'all_passed':all(x['passed'] for x in result)}
pathlib.Path('/var/lib/vz/rumah-deploy/20261027/public-assets-verified.json').write_text(json.dumps(out,indent=2))
print(json.dumps({'anonymous_assets_verified':len(result),'all_passed':out['all_passed']}))
if not out['all_passed']:
    print(json.dumps([x for x in result if not x['passed']]))
    raise SystemExit(1)
'''.replace('ASSETS',repr(assets))
(w/'verify_assets.sh').write_text("set -euo pipefail\npython3 - <<'PY'\n"+program+"\nPY\n",encoding='utf-8')
print(f'Prepared {len(assets)} public asset checks.')
