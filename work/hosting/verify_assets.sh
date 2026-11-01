set -euo pipefail
python3 - <<'PY'
import subprocess,hashlib,json,concurrent.futures,datetime,pathlib,re
assets=[{'path': 'cameras.json', 'bytes': 782387, 'sha256': 'b4ee124d0f0438d892e9cedd46bb342a9f96897713d0b39b783fb281776f5491'}, {'path': 'index.html', 'bytes': 3654, 'sha256': '735f7855c6c9b9a7167b0ba5fe37b11a43988b1986d2855cc4ba5282936fa570'}, {'path': 'robots.txt', 'bytes': 28, 'sha256': 'a8f31103361fca68bef71fc69cff844b7c23bd3d64d2b872d74690cbda656bfc'}, {'path': 'room-viewer.bundle.js', 'bytes': 685400, 'sha256': '2b4f9bab1bcc63a3760910f1cb2be62cb1c5ac26db7a112730871b4a7d7d1d64'}, {'path': 'sources/frame_0000903.jpg', 'bytes': 218338, 'sha256': '544835ade72c22594fbfad011d60e2358579b71922407f7abdf24509439853a0'}, {'path': 'sources/frame_0000999.jpg', 'bytes': 287839, 'sha256': '3af470bb2687de65bb8f574f06348a7ebda7dc6302bce7aa8f5c49515d1854eb'}, {'path': 'sources/frame_0001398.jpg', 'bytes': 209011, 'sha256': 'a468d1455616eca37fd99c60cfe22bff7b02eca88b601a60642cb3cfde16aa41'}, {'path': 'sources/frame_0001612.jpg', 'bytes': 263857, 'sha256': '43a803084c79304cdc3abef83f42f73c3207bf39d590c7474d752fbbdb233a55'}, {'path': 'sources/frame_0002402.jpg', 'bytes': 274875, 'sha256': '8a4cbada269b96b02bca186868eb6c5583565386ebb5352b09e9073c4b48f5dd'}, {'path': 'sources/frame_0003606.jpg', 'bytes': 259433, 'sha256': '9aafb22ee5af6a806f432622cdbbb405b5551ad1df69773922c2382cacf94f8a'}, {'path': 'sources/frame_0004297.jpg', 'bytes': 223728, 'sha256': 'bff0d428b383a592fca70bc5e7de18109fd3c86e1ca7531f1d53f897354bca36'}, {'path': 'sources/frame_0004400.jpg', 'bytes': 248068, 'sha256': 'e5923f2cef8f1d571329a9767bce8c0e501fefea8926d375a9c58f0d227a9648'}]
def check(item):
    url='https://rumah.shizuku.rest/'+item['path']
    r=subprocess.run(['curl','--silent','--show-error','--fail','--compressed','--location','--proto-redir','=https','--max-time','15',url],capture_output=True,timeout=20)
    data=r.stdout
    digest=hashlib.sha256(data).hexdigest()
    canonical=data
    edge_detection=False
    if item['path']=='index.html' and b'/cdn-cgi/challenge-platform/scripts/jsd/main.js' in data:
        canonical=re.sub(rb'<script>\(function\(\)\{function c\(\).*?</script>',b'',data,flags=re.S)
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

PY
