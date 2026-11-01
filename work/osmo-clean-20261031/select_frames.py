"""Select synchronized, sharper native-resolution frames; never alter the source."""
from pathlib import Path
import cv2, json, subprocess, time, numpy as np

WORK=Path(__file__).resolve().parent
CAP=Path(r'C:/Users/bombe/OneDrive/Documents/ChatGPT/Ruang Kamare/roomscan-reconstruction/data/20261031_OSMO360')
RUN=CAP/'clean-v3'; DS=RUN/'dataset'
SOURCE=CAP/'originals/CAM_20261031005909_0004_D.OSV'
FFMPEG=Path(r'C:/Program Files/ffmpeg/bin/ffmpeg.exe')
FPS=30000/1001
for p in [WORK/'thumbnails/cam0',WORK/'thumbnails/cam1',RUN/'logs',RUN/'analysis',DS/'images/cam0',DS/'images/cam1']:
    p.mkdir(parents=True,exist_ok=True)

def run_decode(filters,outputs,logname):
    cmd=[str(FFMPEG),'-hide_banner','-nostdin','-n','-threads','8','-i',str(SOURCE),'-filter_complex',filters]
    for i,out in enumerate(outputs):cmd+=['-map',f'[c{i}]','-q:v','1','-fps_mode','passthrough',str(out)]
    (RUN/f'analysis/{logname}-command.json').write_text(json.dumps(cmd,indent=2))
    with (RUN/f'logs/{logname}.log').open('wb') as f:subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,check=True)

thumbs=[WORK/f'thumbnails/cam{i}/sample_%06d.jpg' for i in range(2)]
if not all(len(list(p.parent.glob('sample_*.jpg'))) == 652 for p in thumbs):
    if any(list(p.parent.glob('sample_*.jpg')) for p in thumbs):raise RuntimeError('Partial thumbnails exist; inspect, do not overwrite.')
    run_decode(';'.join(f'[0:v:{i}]select=not(mod(n\\,3)),scale=640:640:flags=lanczos,format=yuvj420p[c{i}]' for i in range(2)),thumbs,'thumbnail-decode')
print('Thumbnails complete',flush=True)

yy,xx=np.mgrid[:640,:640]
# Optical interior, excluding black borders and much of the carried-camera body region.
scoremask=((xx-320)**2+(yy-320)**2 < 240**2)&(yy<460)
previous=[None,None];records=[]
for j in range(652):
    sharp=[];motion=[]
    for lens in range(2):
        im=cv2.imread(str(thumbs[lens].parent/f'sample_{j+1:06d}.jpg'),cv2.IMREAD_GRAYSCALE)
        if im is None:raise RuntimeError(f'Missing thumbnail {lens} {j}')
        lap=cv2.Laplacian(im,cv2.CV_32F)
        sharp.append(float(np.var(lap[scoremask])))
        small=cv2.resize(im,(320,320),interpolation=cv2.INTER_AREA)
        if previous[lens] is None:motion.append(0.)
        else:
            flow=cv2.calcOpticalFlowFarneback(previous[lens],small,None,.5,3,15,3,5,1.2,0)
            motion.append(float(np.median(np.linalg.norm(flow,axis=2)[scoremask[::2,::2]])))
        previous[lens]=small
    records.append({'source_frame':j*3,'time_seconds':j*3/FPS,'filename':f'frame_{j*3:06d}.jpg','sharpness':sharp,'image_motion_px_320':motion})
quality=np.array([np.sqrt(max(r['sharpness'][0],.001)*max(r['sharpness'][1],.001)) for r in records])
motion=np.array([np.median(r['image_motion_px_320']) for r in records])
moving=float(np.percentile(motion[1:],80));stationary=float(np.percentile(motion[1:],20))
selected=[];start=0
while start<len(records):
    speed=float(np.median(motion[start:min(start+4,len(records))]))
    width=2 if speed>moving else (4 if speed<stationary else 3)
    end=min(start+width,len(records))
    # Mild center preference prevents choosing a boundary frame for negligible sharpness gain.
    scores=quality[start:end]*(1-.04*np.abs(np.arange(start,end)-(start+end-1)/2))
    k=start+int(np.argmax(scores));selected.append(records[k]);start=end
manifest={'source':str(SOURCE),'fps_numerator':30000,'fps_denominator':1001,'source_frames_per_lens':1955,
    'candidate_stride_frames':3,'selected_pair_count':len(selected),'native_size':[3840,3840],
    'note':'Optical flow is image motion, not verified camera translation. Joint lens sharpness selection; motion-adaptive 2/3/4 candidate windows. Original source preserved. JPEG q1 is an 8-bit training decode; not a claim of lossless 10-bit preservation.',
    'max_selected_gap_seconds':max(b['time_seconds']-a['time_seconds'] for a,b in zip(selected,selected[1:])),
    'selected':selected,'candidates':records}
(WORK/'frame-selection.json').write_text(json.dumps(manifest,indent=2))
(RUN/'analysis/frame-selection.json').write_text(json.dumps(manifest,indent=2))
print(f'Selected {len(selected)} synchronized pairs; native extraction starting',flush=True)
expression='+'.join(f'eq(n\\,{r["source_frame"]})' for r in selected)
outputs=[DS/f'images/cam{i}/selected_%06d.jpg' for i in range(2)]
if any(list(p.parent.glob('*.jpg')) for p in outputs):raise RuntimeError('Native output is not empty; inspect before proceeding.')
run_decode(';'.join(f'[0:v:{i}]select={expression},format=yuvj420p[c{i}]' for i in range(2)),outputs,'native-decode')
for lens in range(2):
    for k,r in enumerate(selected,1):
        old=outputs[lens].parent/f'selected_{k:06d}.jpg';new=outputs[lens].parent/r['filename']
        if new.exists():raise RuntimeError('Refusing destination overwrite')
        old.rename(new)
        im=cv2.imread(str(new))
        if im.shape[:2]!=(3840,3840):raise RuntimeError(f'Wrong dimensions {new}')
manifest['native_decode_complete']=True
(WORK/'frame-selection.json').write_text(json.dumps(manifest,indent=2))
(RUN/'analysis/frame-selection.json').write_text(json.dumps(manifest,indent=2))
print(json.dumps({'complete':True,'pairs':len(selected),'image_dir':str(DS/'images')}),flush=True)
