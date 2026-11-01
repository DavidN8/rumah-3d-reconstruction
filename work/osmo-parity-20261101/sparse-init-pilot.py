"""One matched diagnostic: change only the seed of the RGB-only 3DGS pilot."""
from pathlib import Path
import json,sys,subprocess,hashlib
W=Path(__file__).resolve().parent;CAP=Path('C:/Users/bombe/OneDrive/Documents/ChatGPT/Ruang Kamare/roomscan-reconstruction/data/20261031_OSMO360');prior=CAP/'parity-20261101/pilots/diagnostics/rgb-only-3dgs/request.json';name='sparse-rgb-only';root=prior.parent.parent/name;root.mkdir(exist_ok=True)
if (root/'job.json').exists():raise FileExistsError('Preserve existing pilot')
seed=CAP/'clean-v3/explicit-full-v1/dataset/seed-sparse-train.ply';assert seed.is_file();request=json.loads(prior.read_text());command=request['command'][:]
for flag,value in {'--output-dir-prefix':root/'training','--output-dir-name':name,'--seed-pointcloud':seed}.items():command[command.index(flag)+1]=str(value)
request.update(stage=name,command=command,log=str(root/'train.log'),status=str(root/'job.json'),provenance={'coldStart':True,'baseline':'rgb-only-3dgs, 8k steps, cap 1.5M, identical pilot RGB/masks/poses','onlyChangedTrainingInput':'Sparse train-only seed replaces depth-derived dense seed. No depth/normal loads or geometry losses.','seed':str(seed),'seedSha256':hashlib.sha256(seed.read_bytes()).hexdigest(),'notAFullRebuild':True,'deploymentAuthorized':False})
file=root/'request.json';file.write_text(json.dumps(request,indent=2));raise SystemExit(subprocess.call([sys.executable,str(W/'run_logged_job.py'),str(file)]))
