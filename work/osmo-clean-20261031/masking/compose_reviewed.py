"""Compose corrected operator masks without accepting broad semantic detections.

Keep the detected component connected to the carried-camera grip at the native
bottom of each lens. This removes disconnected chairs, slippers and laundry.
Additional clothing masks recover trousers omitted by the general person prompt.
Real shadows are accepted only inside reviewed spatial/time regions. Explicit
head contours cover verified whole-head/silhouette misses. Every output still
requires contact-sheet review before it is marked reviewed/finalized.
"""
from pathlib import Path
import json,argparse
import cv2,numpy as np
from PIL import Image
from build_masks import polygon_mask,write_json

HERE=Path(__file__).resolve().parent
MANIFEST=json.loads((HERE.parent/'frame-selection.json').read_text())
ANNOTATIONS=HERE/'review-annotations.json'

HEAD_EARLY=[[450,447],[482,439],[511,444],[528,458],[538,485],[536,517],
 [523,549],[493,567],[453,576],[417,578],[397,568],[399,542],[410,523],[414,483],[431,459]]
HEAD_741=[[477,411],[513,410],[535,420],[547,445],[549,479],[538,506],
 [515,533],[472,553],[420,563],[385,547],[390,519],[405,485],[430,456],[454,430]]
HEAD_LATE=[[470,419],[505,414],[529,422],[543,444],[546,479],[539,512],
 [519,535],[481,548],[447,543],[429,526],[431,496],[426,478],[438,455],[454,433]]

def shadows(cam,n):
    if cam=='cam0' and 288<=n<=420:
        return [[[.40,.53],[.92,.53],[.92,.90],[.40,.90]]]
    if cam=='cam0' and 750<=n<=822:
        return [[[.06,.48],[.51,.48],[.51,.90],[.06,.90]]]
    if cam=='cam1' and 1272<=n<=1374:
        return [[[.15,.18],[.78,.18],[.78,.84],[.15,.84]]]
    if cam=='cam1' and 1551<=n<=1575:
        return [[[.15,.25],[.82,.25],[.82,.78],[.15,.78]]]
    return []

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--cameras',nargs='+',default=['cam0','cam1'])
    parser.add_argument('--source-frames',nargs='+',type=int)
    args=parser.parse_args()
    annotations=json.loads(ANNOTATIONS.read_text())
    audit=HERE/'composition-audit.json'
    records=[r for r in MANIFEST['selected'] if not args.source_frames or r['source_frame'] in args.source_frames]
    replaced={(cam,r['source_frame']) for cam in args.cameras for r in records}
    rows=[r for r in json.loads(audit.read_text())['frames'] if (r['camera'],r['source_frame']) not in replaced] if audit.exists() else []
    for cam in args.cameras:
        out=HERE/'operator-reviewed'/cam;out.mkdir(parents=True,exist_ok=True)
        for record in records:
            n=record['source_frame'];name=Path(record['filename']).with_suffix('.png')
            raw=np.asarray(Image.open(HERE/'narrow/operator-raw'/cam/name).convert('L'))<128
            cloth=HERE/'clothing/operator-raw'/cam/name
            if 30<=record['time_seconds']<=60 and not cloth.exists():
                raise FileNotFoundError(f'Clothing inference is incomplete: {cloth}')
            if cloth.exists():
                raw|=np.asarray(Image.open(cloth).convert('L'))<128
            if cam=='cam1':
                upper=HERE/'upper-body/operator-raw'/cam/name
                if not upper.exists():raise FileNotFoundError(upper)
                raw|=np.asarray(Image.open(upper).convert('L'))<128
            elif (HERE/'tail-head/operator-raw'/cam/name).exists():
                raw|=np.asarray(Image.open(HERE/'tail-head/operator-raw'/cam/name).convert('L'))<128
            # Small morphological closing joins broken boundary pixels; it does
            # not stand in for a missing leg/head and is followed by visual QA.
            raw=cv2.morphologyEx(raw.astype(np.uint8),cv2.MORPH_CLOSE,
                                cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(17,17)))
            count,labels,stats,_=cv2.connectedComponentsWithStats(raw,8)
            seed_x,seed_y=1920,int(.925*3840)
            label=int(labels[seed_y,seed_x])
            if label==0:
                ys,xs=np.nonzero(raw[3000:3800,1000:2800])
                if not len(xs):
                    raise RuntimeError(f'No masked grip region: {cam}/{name}')
                best=np.argmin((xs+1000-seed_x)**2+(ys+3000-seed_y)**2)
                label=int(labels[ys[best]+3000,xs[best]+1000])
            keep_labels={label}
            entry=annotations['frames'][cam+'/'+record['filename']]
            for x,y in entry.get('retain_operator_components_at',[]):
                hit=int(labels[min(3839,int(y*3840)),min(3839,int(x*3840))])
                if hit:keep_labels.add(hit)
            output=np.isin(labels,list(keep_labels)).astype(np.uint8)
            # Fill enclosed silhouette holes only below 20k native pixels.
            hc,hl,hs,_=cv2.connectedComponentsWithStats(1-output,8)
            filled=0
            for k in range(1,hc):
                x,y,w,h,area=hs[k]
                if x>0 and y>0 and x+w<3840 and y+h<3840 and area<=20000:
                    output[hl==k]=1;filled+=int(area)
            shadow_rois=shadows(cam,n)
            if shadow_rois:
                broad=np.asarray(Image.open(HERE/'operator-raw'/cam/name).convert('L'))<128
                output|=broad & (polygon_mask(output.shape,shadow_rois)>0)
            head=[]
            if cam=='cam1' and n in [255,267,276,288,297,306,318,330]:head=HEAD_EARLY
            if cam=='cam1' and n==741:head=HEAD_741
            if cam=='cam1' and n in [837,843,852,861]:head=HEAD_LATE
            if head:
                output|=polygon_mask(output.shape,[[[x/640,y/640] for x,y in head]])>0
            # Manual static restorations are reviewed against original images.
            # Calibrated perspective additions preserve detached real legs.
            restores=entry.get('restore_static_polygons',[])
            if restores:
                output[polygon_mask(output.shape,restores)>0]=0
            addition_path=HERE/'operator-additions'/cam/name
            additions=np.asarray(Image.open(addition_path).convert('L'))>127 if addition_path.exists() else np.zeros_like(output,dtype=bool)
            output|=additions
            Image.fromarray((1-output)*255).save(out/name)
            rows.append({'camera':cam,'source_frame':n,'filename':record['filename'],
                         'narrow_plus_clothing_fraction':float(raw.mean()),
                         'reviewed_operator_fraction':float(output.mean()),
                         'pruned_components':count-1-len(keep_labels),
                         'main_component_area':int(stats[label,cv2.CC_STAT_AREA]),
                         'small_hole_filled_px':filled,'explicit_head_repair':bool(head),
                         'pinhole_addition_pixels':int(additions.sum()),
                         'static_restoration_polygon_count':len(restores),
                         'reviewed_shadow_rois':shadow_rois})
    write_json(HERE/'composition-audit.json',{'frames':rows,'notes':__doc__})
    print('Composed452 operator masks. Visual review still required before finalization.')

if __name__=='__main__':main()
