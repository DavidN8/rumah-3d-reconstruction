"""Export real camera presets with mandatory validated occupied-room framing."""
from pathlib import Path
import argparse,json,importlib.util
import numpy as np
HERE=Path(__file__).resolve().parent;ORIGINAL=HERE.parent.parent/'osmo-clean-20261031/review/export-clean-cameras.py'
P=argparse.ArgumentParser(description=__doc__)
for flag in ['dataset','selection','normalization','output','bounds-json']:P.add_argument('--'+flag,type=Path,required=True)
P.add_argument('--times',default='1,12,20,25,40,52,60');P.add_argument('--split',choices=['all','train','eval'],default='all');P.add_argument('--lens',default='cam0');P.add_argument('--size',type=int,default=1600);args=P.parse_args()
if args.output.exists():raise FileExistsError(args.output)
occupied=json.loads(args.bounds_json.read_text());bounds=np.asarray(occupied['bounds']);points=np.asarray(occupied['framingPoints']).reshape(-1,3)
if bounds.shape!=(2,3) or not np.isfinite(bounds).all() or not np.all(bounds[1]>bounds[0]):raise ValueError('Invalid occupied room bounds')
if len(points)<1000 or not np.isfinite(points).all() or np.any(points<bounds[0]-1e-4) or np.any(points>bounds[1]+1e-4):raise ValueError('Occupied samples do not match framing bounds')
if not occupied.get('occupiedShell',{}).get('fittedPlanes'):raise ValueError('Fitted floor/ceiling evidence is required')
spec=importlib.util.spec_from_file_location('source_cameras',ORIGINAL);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
# The legacy source exporter is reused for checked ray calibration only. Its raw
# sparse min/max path is replaced in memory, with the original file unchanged.
module.sparse_bounds=lambda unused:occupied['bounds'];module.export(args)
result=json.loads(args.output.read_text());result.update(bounds=occupied['bounds'],boundsSource=occupied['boundsSource'],framingPoints=occupied['framingPoints'],occupiedShell=occupied['occupiedShell']);args.output.write_text(json.dumps(result,indent=2))
print('Exported calibrated references with validated occupied-room framing; no raw sparse bounds fallback')
