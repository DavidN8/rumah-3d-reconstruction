"""Synthetic test of the exact face-carving shader, including timestamp dedup."""
from pathlib import Path
import sys,re,json
import numpy as np
W=Path(__file__).resolve().parent;sys.path.insert(0,str(W.parent.parent/'osmo-improve-20261031/pydeps'));import moderngl
source=(W/'carve-poisson.py').read_text();glsl=re.search(r"ctx.compute_shader\('''(.*?)'''\)",source,re.S).group(1);ctx=moderngl.create_standalone_context(require=430);shader=ctx.compute_shader(glsl)
p=np.array([[0,0,1],[0,0,3],[0,0,4],[1.1,.3,3],[0,0,-1]],'f4');N=len(p)
positions=ctx.buffer(np.column_stack([p,np.ones(N)]).astype('f4').tobytes());positions.bind_to_storage_buffer(0);seen=ctx.buffer(reserve=N*32);seen.clear();seen.bind_to_storage_buffer(1);match=ctx.buffer(reserve=N*4);match.clear();match.bind_to_storage_buffer(2)
S=128;f=64;yy,xx=np.mgrid[:S,:S];rays=np.stack([(xx-S/2)/f,(yy-S/2)/f,np.ones_like(xx)],axis=-1);shader['ranges'].value=0;shader['count'].value=N;shader['K'].value=(f,f,S/2,S/2);shader['size'].value=(S,S)
for timestamp in range(5):
    angle=(timestamp-2)*.08;co,si=np.cos(angle),np.sin(angle);R=np.array([[co,0,si],[0,1,0],[-si,0,co]]);C=np.array([(timestamp-2)*.08,0,.1]);world_rays=rays@R;multiplier=(3-C[2])/world_rays[...,2];raw=np.rint(np.linalg.norm(rays,axis=2)*multiplier*1000).astype('u2');tex=ctx.texture((S,S),1,raw.tobytes(),dtype='u2');tex.use(0)
    shader['R'].write(np.asarray(R.T,'f4').tobytes());shader['t'].value=tuple(-R@C);shader['word'].value=0;shader['bitmask'].value=1<<timestamp
    # Four virtual faces at the same timestamp must count as ONE observation.
    for repeat in range(4):shader.run(1);ctx.memory_barrier()
    tex.release()
ctx.finish();counts=np.bitwise_count(np.frombuffer(seen.read(),dtype='u4').reshape(N,8)).sum(axis=1);support=np.frombuffer(match.read(),dtype='u4')>0
assert counts[0]==5 and not support[0],(counts,support)
assert support[1] and support[3] and counts[1]==0,(counts,support)
assert counts[2]==0 and counts[4]==0,(counts,support)
before=seen.read();empty=ctx.texture((S,S),1,np.zeros((S,S),'u2').tobytes(),dtype='u2');empty.use(0);shader['bitmask'].value=1<<9;shader.run(1);ctx.memory_barrier();ctx.finish();assert seen.read()==before
report={'passed':True,'exactProductionShader':True,'checks':['Euclidean ray range under translated/rotated cameras','Five independent timestamps carve a false closure','Four virtual faces per timestamp count once','Observed surface protected','Behind-surface and behind-camera faces retained','Invalid depth contributes zero observations'],'counts':counts.tolist(),'support':support.tolist()};(W/'poisson-pilot/carve-tests.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
