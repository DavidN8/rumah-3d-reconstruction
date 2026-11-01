from pathlib import Path
import cv2,json,numpy as np
RUN=Path(r'C:\Users\bombe\OneDrive\Documents\ChatGPT\Ruang Kamare\roomscan-reconstruction\data\20261031_OSMO360\lite-v1')
DS=RUN/'dataset';record=json.loads((RUN/'analysis/seed-fisheye.json').read_text())
assert record['status']=='complete'
out=DS/'depths-aligned'
if out.exists():raise RuntimeError('Aligned depth directory already exists.')
rows=[]
for name,fit in record['frames'].items():
    if not fit['accepted_fit']:continue
    raw=cv2.imread(fit['raw_depth_path'],-1);assert raw.dtype==np.uint16
    depth=raw.astype(np.float64)*.001*fit['scale']+fit['offset']
    mask=cv2.imread(fit['mask_path'],0);assert mask is not None
    mask=cv2.resize(mask,(raw.shape[1],raw.shape[0]),interpolation=cv2.INTER_NEAREST)>127
    valid=(raw>0)&mask&np.isfinite(depth)&(depth>.05)&(depth<30)
    converted=np.where(valid,np.round(depth*1000),0).astype(np.uint16)
    path=(out/name).with_suffix('.png');path.parent.mkdir(parents=True,exist_ok=True)
    assert cv2.imwrite(str(path),converted)
    assert np.max(np.abs(converted[valid]*.001-depth[valid]))<=.000501
    rows.append({'name':name,'scale':fit['scale'],'offset':fit['offset'],'valid_fraction':float(valid.mean())})
report={'depth_units':'millimetres in normalized SfM frame (approximate physical scale)','ray_depth':True,
        'source_maps_unchanged':True,'aligned_views':len(rows),'rgb_normal_views_without_depth':record['registered_frames']-len(rows),
        'fits':rows}
(RUN/'analysis/depth-supervision.json').write_text(json.dumps(report,indent=2));print(json.dumps({k:v for k,v in report.items() if k!='fits'}))
