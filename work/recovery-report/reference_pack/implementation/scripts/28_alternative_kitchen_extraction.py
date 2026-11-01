"""Bounded test of Argon's alternative 0.65 / 640 kitchen extraction."""
from pathlib import Path
from importlib.machinery import SourceFileLoader
import subprocess,time,os
core=SourceFileLoader('alternative_core',str(Path(__file__).with_name('20_component_recovery.py'))).load_module()
BASE,RUN=core.BASE,core.RUN
dest=RUN/'exports/alternative-kitchen';dest.mkdir(exist_ok=True)
if (dest/'zone-kitchen.glb').exists():raise RuntimeError('Alternative extraction already exists; preserve it')
cmd=[str(core.SPIRULA),'mesh',str(RUN/'training/zone-kitchen'),'--data',str(RUN/'datasets/zone-kitchen'),'--output',str(dest/'zone-kitchen'),'--format','glb+jpeg90','--color','texture','--texture-size','8192','--num-threads','16','--merge-factor','0.65','--max-grid-res','640','--bisection-iters','4','--carve-k','3','--fill-hole-ratio','0','--fill-hole-max-edges','64','--floater-min-faces','50','--device','auto']
env=os.environ.copy();env['OMP_NUM_THREADS']='16'
for k in ['CUDA_VISIBLE_DEVICES','GPU_DUTY_CYCLE','SS_GPU_DUTY_CYCLE']:env.pop(k,None)
record={'purpose':'Test the mandate alternative on the existing corrected kitchen checkpoint; no retraining or promotion assumed','command':cmd,'stage':'running'};core.save(RUN/'analysis/alternative-kitchen-extraction.json',record);t=time.monotonic()
with (RUN/'logs/alternative-kitchen-extraction.log').open('wb',buffering=0) as log:r=subprocess.run(cmd,cwd=BASE,env=env,stdout=log,stderr=subprocess.STDOUT)
record.update(exit_code=r.returncode,elapsed_seconds=time.monotonic()-t,stage='completed' if r.returncode==0 else 'failed');core.save(RUN/'analysis/alternative-kitchen-extraction.json',record)
print(record,flush=True)
raise SystemExit(r.returncode)
