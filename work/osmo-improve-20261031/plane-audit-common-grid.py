"""Compare unchanged baseline/v4 on identical plane-grid cells, excluding openings."""
from pathlib import Path
import json
import numpy as np
HERE=Path(__file__).resolve().parent
base=json.loads((HERE/'plane-audit-summary.json').read_text(encoding='utf-8'))
v4=json.loads((HERE/'plane-audit-v4-summary.json').read_text(encoding='utf-8'))
old=np.load(HERE/'plane-audit-grid.npz',allow_pickle=False)
new=np.load(HERE/'plane-audit-v4-grid.npz',allow_pickle=False)

def measure(distance,mask,neighbor_pairs):
    selected=distance[mask];center=float(np.median(selected));deviation=np.abs(selected-center)
    adjacent=np.concatenate([np.abs(distance[first]-distance[second]) for first,second in neighbor_pairs])
    return {'signed_median':center,'absolute_median':float(np.median(np.abs(selected))),
      'absolute_p90':float(np.percentile(np.abs(selected),90)),
      'centered_absolute_median':float(np.median(deviation)),
      'centered_absolute_p90':float(np.percentile(deviation,90)),
      'adjacent_5cm_step_median_difference':float(np.median(adjacent)),
      'adjacent_5cm_step_p90_difference':float(np.percentile(adjacent,90)),
      'adjacent_pairs':len(adjacent)}

rows=[]
for before,after in zip(base['planes'],v4['planes']):
    number=before['plane'];key=f'plane_{number}_'
    assert number==after['plane'] and before['normal']==after['normal'] and before['offset']==after['offset']
    assert np.array_equal(old[key+'uv'],new[key+'uv'])
    assert np.array_equal(old[key+'inside'],new[key+'inside'])
    assert np.array_equal(old[key+'negative'],new[key+'negative'])
    d0=old[key+'signed'];d1=new[key+'signed']
    eligible=old[key+'inside']&~old[key+'negative']
    common=eligible&np.isfinite(d0)&np.isfinite(d1)&(np.abs(d0)<=.20)&(np.abs(d1)<=.20)
    nv,nu=old[key+'shape'];index=np.arange(len(common)).reshape(nv,nu);gridmask=common.reshape(nv,nu)
    pairs=[]
    for first,second,valid in ((index[:,:-1],index[:,1:],gridmask[:,:-1]&gridmask[:,1:]),
                               (index[:-1,:],index[1:,:],gridmask[:-1,:]&gridmask[1:,:])):
        pairs.append((first[valid],second[valid]))
    if common.sum()<20:continue
    row={'plane':number,'kind':before['kind'],'support_points':before['support_points'],
      'distinct_images':before['distinct_images'],'grid_cell_size':.05,'eligible_cells_excluding_negative_witnesses':int(eligible.sum()),
      'common_hit_cells_within20cm':int(common.sum()),'baseline':measure(d0,common,pairs),'v4':measure(d1,common,pairs)}
    rows.append(row)
    b=row['baseline'];a=row['v4']
    print(number,before['kind'],'common',common.sum(),
      'centered-p90 cm',round(100*b['centered_absolute_p90'],2),'->',round(100*a['centered_absolute_p90'],2),
      'neighbor-p90 cm',round(100*b['adjacent_5cm_step_p90_difference'],2),'->',round(100*a['adjacent_5cm_step_p90_difference'],2))
report={'baseline_source':base['source_mesh'],'baseline_sha256':base['source_mesh_sha256'],
 'v4_source':v4['source_mesh'],'v4_sha256':v4['source_mesh_sha256'],'same_plane_equations_and_grid':True,
 'units':'Approximate scene units; centimetre displays multiply by100 using assumed1.5m camera-height normalization.',
 'selection':'Identical inside-hull5cm grid cells, excluding cells crossed by>=2 trusted background feature rays; both meshes hit within20cm of plane.',
 'method':'Closest normal-ray surface from either side of the plane. Centered spread subtracts each mesh signed median, separating offset from waviness. Neighbor differences use identical valid5cm grid edges.',
 'limitations':['Same-SfM evidence, not independent measured geometry.','The20cm slab may still include nearby furniture or parallel wall layers.','Common cells measure shape only; added/missing coverage is reported separately.'],
 'geometry_mutated':False,'gpu_used':False,'rows':rows}
(HERE/'plane-audit-v4-common-grid.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
