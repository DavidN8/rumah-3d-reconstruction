"""Compare exactly paired CPU visibility observations, without rendering/GPU."""
import argparse
import json
from pathlib import Path
import numpy as np

HERE=Path(__file__).resolve().parent

def main():
    p=argparse.ArgumentParser();p.add_argument('--reference',required=True);p.add_argument('--candidate',required=True);p.add_argument('--out',required=True);a=p.parse_args()
    reference=Path(a.reference).resolve();candidate=Path(a.candidate).resolve();out=Path(a.out).resolve()
    if not out.is_relative_to(HERE) or not out.name.startswith('qa-'):raise ValueError('Own qa-* output path required')
    rmeta=json.loads(reference.read_text(encoding='utf-8-sig'));cmeta=json.loads(candidate.read_text(encoding='utf-8-sig'))
    assert rmeta['ray_sample']['cache_sha256']==cmeta['ray_sample']['cache_sha256']
    old=np.load(reference.with_suffix('.npz'));new=np.load(candidate.with_suffix('.npz'))
    np.testing.assert_array_equal(old['expected_range'],new['expected_range'])
    names=np.load(HERE/'qa-fixed-rays.npz')['names']
    categories=['near','early','behind','missing']
    matrix={source:{target:int(np.count_nonzero(old[source]&new[target])) for target in categories} for source in categories}
    improve=~old['near']&new['near'];regress=old['near']&~new['near']
    newearly=~old['early']&new['early'];resolvedearly=old['early']&~new['early']
    images=[]
    for name in sorted(set(names)):
        ix=names==name
        row={'name':str(name),'new_near':int(np.count_nonzero(ix&improve)),'lost_near':int(np.count_nonzero(ix&regress)), 'new_early':int(np.count_nonzero(ix&newearly)),'resolved_early':int(np.count_nonzero(ix&resolvedearly))}
        if any(row[key] for key in ('new_near','lost_near','new_early','resolved_early')):images.append(row)
    result={'reference':rmeta['label'],'candidate':cmeta['label'],'observation_count':len(names),'in_sample_consistency_only':True,'matrix_reference_row_candidate_column':matrix,'new_near':int(improve.sum()),'lost_near':int(regress.sum()),'new_early':int(newearly.sum()),'resolved_early':int(resolvedearly.sum()),'per_changed_image':images}
    out.write_text(json.dumps(result,indent=2));print(json.dumps({k:v for k,v in result.items() if k!='per_changed_image'},indent=2))

if __name__=='__main__':main()
