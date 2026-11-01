"""Read-only comparison and CPU Gaussian scale audit of retained local runs."""
import json
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
DATA = Path(r'C:\Users\bombe\OneDrive\Documents\ChatGPT\Ruang Kamare\roomscan-reconstruction\data')
IPHONE = DATA/'20261027_IPHONE_WIDE/recovery-v2/training/zone-living-bedroom-allviews'
OSMO = DATA/'20261031_OSMO360/lite-v1/training/osmo-lite-trusted-v3'

def ply_scales(path):
    with path.open('rb') as f:
        header = []
        while True:
            line = f.readline().decode('ascii').strip()
            header.append(line)
            if line == 'end_header': break
        offset = f.tell()
    assert 'format binary_little_endian 1.0' in header
    count = int(next(x for x in header if x.startswith('element vertex ')).split()[-1])
    props = [x.split()[-1] for x in header if x.startswith('property float ')]
    assert len(props) == sum(x.startswith('property ') for x in header)
    points = np.memmap(path, dtype=np.dtype([(p,'<f4') for p in props]), mode='r', offset=offset, shape=(count,))
    scales = np.exp(np.stack([points[f'scale_{i}'] for i in range(3)], axis=1).astype(np.float64))
    largest = scales.max(axis=1)
    opacity = 1/(1+np.exp(-np.clip(points['opacity'].astype(np.float64), -60, 60)))
    result = {'path':str(path), 'count':count, 'interpretation':'PLY scale_0/1/2 are natural log standard deviations; values below are exp(log_scale) in unchanged training/world frame.', 'max_axis_quantiles':dict(zip(['0','25','50','75','90','95','99','99.9','100'], np.percentile(largest,[0,25,50,75,90,95,99,99.9,100]).tolist())), 'opacity_quantiles':dict(zip(['1','10','50','90','99'],np.percentile(opacity,[1,10,50,90,99]).tolist())), 'thresholds':{}}
    for limit in [.08,.12,.16,.2,.3,.5,1]:
        changed=largest>limit
        ratios=np.minimum(scales,limit).prod(axis=1)/scales.prod(axis=1)
        result['thresholds'][str(limit)]={'splats_changed':int(changed.sum()),'fraction_changed':float(changed.mean()),'opacity_mass_fraction_changed':float(opacity[changed].sum()/opacity.sum()),'median_volume_ratio_changed':float(np.median(ratios[changed])) if changed.any() else 1,'splats_above_opacity_05_changed':int(np.count_nonzero(changed&(opacity>.5)))}
    return result

def main():
    configs = {'iphone':json.loads((IPHONE/'config.json').read_text()),'osmo_v3':json.loads((OSMO/'config.json').read_text())}
    keys=['preset','num_iterations','cap_max','max_world_size','max_screen_size','max_screen_size_clip_hardness','max_screen_size_penalty','normal_reg_weight','normal_supervision_weight','depth_supervision_weight','depth_distortion_reg','normal_distortion_reg','rgb_distortion_reg','mean_median_depth_weight','median_depth_normal_reg_weight','median_normal_supervision_weight','median_render_normal_reg_weight','opacity_reg','opacity_reg_decay_power','scale_reg','scale_reg_decay_power','scale_regularization_weight','scales_lr','scales_lr_final','sh_reg','sh_degree','refine_every','refine_start_iter','refine_stop_iter','refine_stop_num_iter','max_split_fraction','densify_oversize_split_fraction','densify_oversize_score_blend','use_revised_densification','use_long_axis_split','auto_scale_poses','train_frame','depth_dir','input_depth_is_ray_depth','warp_to_pinhole','apply_loss_for_mask']
    comparison={key:{name:config.get(key,'<missing>') for name,config in configs.items()} for key in keys}
    result={'configs':{name:str((IPHONE if name=='iphone' else OSMO)/'config.json') for name in configs}, 'comparison':comparison, 'scale_audit':ply_scales(OSMO/'step-000040000.ckpt/splat.ply')}
    result['effective_growth_stop']={name:max(c['refine_stop_iter'],c['num_iterations']-c['refine_stop_num_iter']) for name,c in configs.items()}
    output=HERE/'qa-training-config.json';output.write_text(json.dumps(result,indent=2));print(json.dumps({'output':str(output),'scale_audit':result['scale_audit'],'effective_growth_stop':result['effective_growth_stop']},indent=2))

if __name__=='__main__':main()
