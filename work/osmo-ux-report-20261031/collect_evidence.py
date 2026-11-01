from pathlib import Path
import json,hashlib,shutil,math
from PIL import Image,ImageDraw,ImageFont
W=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent
O=W/'work/osmo-clean-20261031';R=O/'review';P=R/'production'
D=Path('C:/Users/bombe/OneDrive/Documents/ChatGPT/Ruang Kamare/roomscan-reconstruction/data')
FULL=D/'20261031_OSMO360/clean-v3/explicit-full-v1';IP=D/'20261027_IPHONE_WIDE/recovery-v2'
def load(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
sources={};evidence=[]
def add(key,path,label=None):
    path=Path(path);assert path.is_file(),path
    row={'id':f'E{len(evidence)+1:02d}','key':key,'path':str(path),'label':label or path.name,'bytes':path.stat().st_size,'sha256':sha(path)}
    sources[key]=row;evidence.append(row);return path
for key,path in {
 'user':HERE/'assets/user-latest-osmo.png','manifest':P/'public/room-be410c75b8.json',
 'viewer':P/'room-viewer.js','policy':P/'native-delivery.js','cameras':R/'clean-cameras.json',
 'camera_export':R/'export-clean-cameras.py','full_config':FULL/'training/osmo-explicit-depth-v1/config.json',
 'full_train_job':O/'explicit-full-train-job.json','geometry_job':O/'explicit-full-geometry-job.json',
 'pinhole':FULL/'dataset/explicit-pinhole-audit.json','scale':FULL/'dataset/depth-scale-audit.json',
 'trusted':FULL/'dataset/trusted-depth-and-seed-audit.json','sfm':O/'geometry/fresh-sfm-preparation-audit.json',
 'selection':O/'frame-selection.json','masks':O/'masking/masks-ready.json',
 'matched':R/'clean-matched-review.json','native_eval':FULL/'analysis/valid-native-evaluation.json',
 'packing':R/'clean-final.sog.json','review':R/'full-final-review.json','public':P/'deployment/public-browser-verification.json',
 'browser':P/'final-browser-verification.json','release_gate':P/'release-approval.json',
 'iphone_fast':W/'work/mobile-20261029/phone-asset-report.json','iphone_native':IP/'analysis/allviews-raw-verification.json',
 'iphone_coverage':IP/'analysis/all-usable-coverage.json','iphone_height':W/'outputs/Rumah_Full_Height_Verification_2026-10-29.json',
 'iphone_report':W/'work/recovery-report/build_recovery_report.py','historical':W/'work/report/reference_pack/manifest.json',
 'graph':HERE/'graphify-out/summary.json','pilot':R/'bath-pilot-review.json',
 'visibility':R/'visibility-experiment-result.json'
}.items():add(key,path)
image_paths={
 'iphone_dollhouse':W/'outputs/Rumah_Full_Height_2026-10-29.jpg',
 'iphone_phone':W/'outputs/Rumah_Phone_View_2026-10-29.jpg',
 'iphone_overview_native':W/'outputs/iPhone_Wide_Rebuilt_Overview.png',
 'historical_nikon':W/'work/report/reference_pack/images/F04-codex-nikon-034.png',
 'historical_samsung':W/'work/report/reference_pack/images/F03-samsung-accepted.png',
 'before_after':R/'renders/full-rebuild-bathroom-before-after.jpg',
 'worst_eval':R/'renders/full-eval-six-worst-valid.jpg',
 'native_zero':R/'renders/full-native-eval-zero.jpg',
 'source_seven':R/'source-qa-seven.jpg',
 'sfm_continuity':O/'geometry/fresh-sfm-preparation-audit-continuity.png',
 'mirror_masks':O/'geometry/second-mirror-cam1-outline-review.jpg',
}
images={}
for key,path in image_paths.items():
    if path.is_file():
        add(key,path);target=HERE/'assets'/(key+path.suffix);shutil.copy2(path,target);images[key]={'path':str(target),'dimensions':Image.open(path).size}
cameras=load(sources['cameras']['path']);matched=load(sources['matched']['path'])
for i,preset in enumerate(cameras['presets'],1):
    for label,path in [('source',Path(preset['sourceFile'])),('native',R/f'renders/clean-fullNative-pose-{i}.png'),('sog',R/f'renders/clean-fullSog-pose-{i}.png')]:
        add(f'pose{i}_{label}',path);images[f'pose{i}_{label}']={'path':str(path),'dimensions':Image.open(path).size}
font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',20)
# Diagnostic crops preserve the exact source/render pixels. Enlargement is
# nearest-neighbour for visibility, not sharpening or generative repair.
regions=[('fridge_detail',1,(330,340,530,570)),('floor_fan_detail',7,(50,220,300,480)),('bath_detail',6,(180,110,455,390))]
for key,i,box in regions:
    sheet=Image.new('RGB',(900,370),'#192028');draw=ImageDraw.Draw(sheet)
    for col,label in enumerate(['source','native','sog']):
        im=Image.open(images[f'pose{i}_{label}']['path']).convert('RGB').resize((600,600),Image.Resampling.LANCZOS)
        crop=im.crop(box);crop.thumbnail((286,320),Image.Resampling.NEAREST)
        draw.text((col*300+8,9),{'source':'Source photograph','native':'Original Gaussian','sog':'Same model / SOG'}[label],font=font,fill='white');sheet.paste(crop,(col*300+(300-crop.width)//2,43))
    target=HERE/'assets'/(key+'.png');sheet.save(target);images[key]={'path':str(target),'dimensions':sheet.size}
# Per-view source/SOG comparisons avoid shrinking all seven views onto one page.
for i in [1,2,3,4,5,6,7]:
    sheet=Image.new('RGB',(1200,638),'#192028');draw=ImageDraw.Draw(sheet)
    for col,label in enumerate(['source','sog']):
        draw.text((col*600+10,10),'Source photograph' if col==0 else 'Delivered Osmo Gaussian / full source draw',font=font,fill='white')
        sheet.paste(Image.open(images[f'pose{i}_{label}']['path']).convert('RGB').resize((600,600),Image.Resampling.LANCZOS),(col*600,38))
    target=HERE/'assets'/f'pair-{i}.jpg';sheet.save(target,quality=95);images[f'pair{i}']={'path':str(target),'dimensions':sheet.size}
selection=load(sources['selection']['path']);pinhole=load(sources['pinhole']['path']);trusted=load(sources['trusted']['path']);ev=load(sources['native_eval']['path']);scale=load(sources['scale']['path'])
native_cameras=O/'geometry/sfm-manifest-native3840.json'
lines=(D/'20261031_OSMO360/clean-v3/dataset/sparse/0/cameras.txt').read_text().splitlines();angular=[]
for line in lines:
    if line.startswith('#') or not line.strip():continue
    values=line.split();fx=float(values[4]);k=list(map(float,values[8:12]));theta=math.pi/4;td=theta*(1+sum(c*theta**(2*(j+1)) for j,c in enumerate(k)))
    angular.append({'camera':int(values[0]),'nativeFocalPixels':fx,'virtualFocalPixels':600,'nativeCenterSamplesPerVirtualCenterPixel':fx/600,'nativeHorizontalPixelSpanAcross90Degrees':2*fx*td,'virtualHorizontalSpanPixels':1200})
metadata={'evidence':evidence,'sources':sources,'images':images,'manifest':load(sources['manifest']['path']),'config':load(sources['full_config']['path']),'trainJob':load(sources['full_train_job']['path']),'geometryJob':load(sources['geometry_job']['path']),'pinhole':{k:v for k,v in pinhole.items() if k not in ['views','sha256','purpose']},'depthScale':{k:v for k,v in scale.items() if k not in ['frames','purpose']},'trusted':{k:v for k,v in trusted.items() if k not in ['frames','method']},'selection':{k:v for k,v in selection.items() if k!='selected'},'nativeEval':{k:v for k,v in ev.items() if k!='rows'},'worstEval':sorted(ev['rows'],key=lambda row:row['psnrDb'])[:6],'matched':matched,'angularSampling':angular,'packing':load(sources['packing']['path']),'public':load(sources['public']['path']),'browser':load(sources['browser']['path']),'iphoneFast':load(sources['iphone_fast']['path']),'iphoneNative':load(sources['iphone_native']['path']),'iphoneCoverage':{k:v for k,v in load(sources['iphone_coverage']['path']).items() if k!='depth_fits'},'sfm':load(sources['sfm']['path']),'graph':load(sources['graph']['path'])}
historical=load(sources['historical']['path']);metadata['historicalRecords']={}
for row in historical['records']:
    if row['id'] in ['S17','S19','S26']:
        file=W/'work/report/reference_pack'/row['file']
        try:content=load(file)
        except json.JSONDecodeError:content=file.read_text(encoding='utf-8-sig')
        metadata['historicalRecords'][row['id']]={'provenance':row,'content':content}
(HERE/'evidence.json').write_text(json.dumps(metadata,indent=2));print(json.dumps({'evidenceFiles':len(evidence),'figuresAvailable':len(images),'userScreenshotDimensions':Image.open(HERE/'assets/user-latest-osmo.png').size,'angularSampling':angular,'all188HeldoutMeanPsnr':ev['meanPsnrDb']},indent=2))
