from pathlib import Path
import json,subprocess,sys
W=Path(__file__).resolve().parent;OLD=W.parent/'osmo-clean-20261031'
ROOT=Path('C:/Users/bombe/OneDrive/Documents/ChatGPT/Ruang Kamare/roomscan-reconstruction/data/20261031_OSMO360/clean-v3/explicit-full-v1')
OUT=W/'review/mesh-pilot';OUT.mkdir(exist_ok=True)
command=[str(OLD/'runtime/spirula-2026.10.30/spirula.exe'),'mesh',str(ROOT/'training/osmo-explicit-depth-v1'),'--data',str(ROOT/'dataset'),'--output',str(OUT/'clean-mesh'),'--format','glb+jpg,ply','--color','texture,vertex','--texture-size','4096','--merge-factor','0.5','--max-grid-res','384','--bisection-iters','4','--carve-k','3','--fill-hole-ratio','0','--fill-hole-max-edges','0','--floater-min-faces','50','--max-cameras','-1','--num-threads','12','--device','0']
job={'stage':'clean-pinhole-native-mesh-pilot','command':command,'cwd':str(W),'log':str(OUT/'mesh.log'),'status':str(OUT/'job.json'),'provenance':{'oldFisheyeMeshReused':False,'checkpoint':'explicit cold depth full 50k','architectRequest':'Option B pilot; inspect, do not deploy blindly'}}
file=OUT/'request.json';file.write_text(json.dumps(job,indent=2))
raise SystemExit(subprocess.call([sys.executable,str(W/'run_logged_job.py'),str(file)]))
