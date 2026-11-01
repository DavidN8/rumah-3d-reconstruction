"""Reproduce the accepted extraction's exact FPS selection at native lens size."""
from pathlib import Path
import json
import subprocess
import time
import cv2
import numpy as np

HERE=Path(__file__).parent
CAPTURE=Path(r'C:\Users\bombe\OneDrive\Documents\ChatGPT\Ruang Kamare\roomscan-reconstruction\data\20261031_OSMO360')
OLD=CAPTURE/'lite-v1/dataset'
DEST=CAPTURE/'recovery-v2/source-full'
FFMPEG=Path(r'C:\Program Files\ffmpeg\bin\ffmpeg.exe')
source=CAPTURE/'originals/CAM_20261031005909_0004_D.OSV'
old_command=json.loads((CAPTURE/'lite-v1/analysis/extract.json').read_text())['command']
# Reuse original command verbatim, substituting output paths and removing only
# the scale filter. This preserves FPS rounding, source stream timestamps,
# stream synchronization, output naming and JPEG quantization settings.
command=old_command.copy()
filter_index=command.index('-filter_complex')+1
original_filter=command[filter_index]
command[filter_index]=original_filter.replace(',scale=1920:1920:flags=lanczos','')
assert command[filter_index]=='[0:v:0]fps=2,format=yuvj420p[c0];[0:v:1]fps=2,format=yuvj420p[c1]'
for camera in (0,1):
    images=DEST/f'images/cam{camera}';masks=DEST/f'masks/cam{camera}'
    images.mkdir(parents=True,exist_ok=True);masks.mkdir(parents=True,exist_ok=True)
    if any(images.glob('*.jpg')):raise RuntimeError('Full source images already exist; refusing overwrite')
    target=str(images/'frame_%06d.jpg')
    old_target=next(v for v in command if f'images/cam{camera}/frame_' in v.replace('\\','/'))
    command[command.index(old_target)]=target
report={'command':command,'original_command':old_command,'exact_fps_filter_preserved':True,'only_extraction_filter_change':'Removed equal1920x1920 Lanczos scale; retained native3840x3840 lens pixels','output':str(DEST),'source':str(source),'started_unix':time.time()}
(HERE/'qa-full-source-extraction.json').write_text(json.dumps(report,indent=2))
print('START native full frames; exact FPS selection retained',flush=True);start=time.monotonic()
with (HERE/'qa-full-source-extraction.log').open('wb',buffering=0) as log:
    result=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT)
report['exit_code']=result.returncode;report['elapsed_seconds']=time.monotonic()-start
if result.returncode:raise RuntimeError((HERE/'qa-full-source-extraction.log').read_text(errors='replace')[-3000:])
comparisons=[]
for camera in (0,1):
    files=sorted((DEST/f'images/cam{camera}').glob('*.jpg'));oldfiles=sorted((OLD/f'images/cam{camera}').glob('*.jpg'))
    assert [p.name for p in files]==[p.name for p in oldfiles] and len(files)==130
    for path in files:
        image=cv2.imread(str(path));assert image.shape[:2]==(3840,3840)
        mask=cv2.imread(str(OLD/f'masks/cam{camera}'/path.with_suffix('.png').name),0)
        assert mask.shape==(1920,1920)
        up=cv2.resize(mask,(3840,3840),interpolation=cv2.INTER_NEAREST)
        cv2.imwrite(str(DEST/f'masks/cam{camera}'/path.with_suffix('.png').name),up)
        if int(path.stem[-6:]) not in (1,25,41,62,87,100,130):continue
        down=cv2.resize(image,(1920,1920),interpolation=cv2.INTER_LANCZOS4).astype(np.float32)
        candidates=[]
        index=int(path.stem[-6:])
        for neighbor in (index-1,index,index+1):
            if not 1<=neighbor<=130:continue
            old=cv2.imread(str(OLD/f'images/cam{camera}/frame_{neighbor:06d}.jpg')).astype(np.float32)
            error=down-old
            candidates.append({'frame':neighbor,'rgb_rmse':float(np.sqrt(np.mean(error*error))),'rgb_mae':float(np.abs(error).mean())})
        same=next(r for r in candidates if r['frame']==index)
        best=min(candidates,key=lambda r:r['rgb_rmse'])
        comparisons.append({'camera':camera,'frame':index,'same_index_is_closest':best['frame']==index,'same_index_rmse':same['rgb_rmse'],'same_index_mae':same['rgb_mae'],'neighbor_comparison':candidates})
report.update(frames_per_lens=130,total_full_resolution_images=260,resolution=[3840,3840],total_rgb_bytes=sum(p.stat().st_size for p in (DEST/'images').rglob('*.jpg')),mask_resize='Exactly2x nearest-neighbor from frozen1920 masks; original masks untouched',intrinsics_change='Multiply fx,fy,cx,cy by2; retain all fisheye distortion coefficients and poses',source_comparisons=comparisons,all_sampled_matches_closest=all(r['same_index_is_closest'] for r in comparisons),sampling_note='JPEG downsample comparisons include JPEG quantization and different FFmpeg/OpenCV Lanczos kernels, so bit identity is not expected.')
(HERE/'qa-full-source-extraction.json').write_text(json.dumps(report,indent=2))
print(json.dumps({k:v for k,v in report.items() if k not in ('command','original_command','source_comparisons')},indent=2),flush=True)
print('Same-index RMSE range',min(r['same_index_rmse'] for r in comparisons),max(r['same_index_rmse'] for r in comparisons),flush=True)
assert report['all_sampled_matches_closest'],'Temporal frame verification failed; inspect report'
