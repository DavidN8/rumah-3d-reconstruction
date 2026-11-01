from pathlib import Path
import json,sys,cv2,numpy as np
from PIL import Image,ImageDraw
W=Path(__file__).resolve().parent
sys.path.insert(0,str(W.parent/'osmo-reconstruct-20261031'))
from seed_fisheye import read_model
R=Path(r'C:/Users/bombe/OneDrive/Documents/ChatGPT/Ruang Kamare/roomscan-reconstruction/data/20261031_OSMO360/clean-v3')
selection=json.loads((W/'frame-selection.json').read_text())['selected']
cameras,images,points=read_model(R/'dataset/sparse/0')
regions={600:[[109,526],[177,558],[211,579],[115,570]],
         1551:[[412,84],[531,130],[574,200],[512,204],[405,143]]}
out=Image.new('RGB',(1280,680),'#192028');draw=ImageDraw.Draw(out);rows=[]
for column,(source,polygon) in enumerate(regions.items()):
    record=next(r for r in selection if r['source_frame']==source)
    name='cam0/'+record['filename'];im=next(v for v in images.values() if v['name']==name)
    photo=Image.open(R/'dataset/images'/name).convert('RGB').resize((640,640))
    layer=Image.new('RGBA',(640,640));ld=ImageDraw.Draw(layer);ld.polygon([tuple(x) for x in polygon],fill=(0,255,255,80),outline='cyan')
    annotated=Image.alpha_composite(photo.convert('RGBA'),layer).convert('RGB')
    coords=im['points2D_xy'];pid=im['point3D_ids'];inside=cv2.fillPoly(np.zeros((3840,3840),np.uint8),[np.asarray(polygon,np.int32)*6],1)
    valid=(pid>=0)&(coords[:,0]>=0)&(coords[:,0]<3840)&(coords[:,1]>=0)&(coords[:,1]<3840)
    selected=[]
    for j in np.flatnonzero(valid):
        if inside[int(coords[j,1]),int(coords[j,0])] and int(pid[j]) in points:
            selected.append(points[int(pid[j])]['xyz'])
    xyz=np.asarray(selected)
    row={'source_frame':source,'camera':'cam0','polygon_640':polygon,'observations':len(selected)}
    if len(selected):row.update(median_xyz=np.median(xyz,axis=0).tolist(),height_percentiles=np.percentile(xyz[:,1],[5,25,50,75,95]).tolist(),height_std=float(np.std(xyz[:,1])))
    rows.append(row);out.paste(annotated,(640*column,40));draw.text((640*column+8,10),f'Source {source}: physical bathroom floor, {len(selected)} points',fill='white')
out.save(W/'review/floor-consistency-regions.jpg',quality=94)
report={'units':'normalized arbitrary units, not metres','method':'Independent scene check using manually identified physical floor pixels in two source frames. These regions are diagnostic only and never modify geometry.','regions':rows}
if all(r['observations'] for r in rows):report['median_floor_height_difference']=abs(rows[0]['height_percentiles'][2]-rows[1]['height_percentiles'][2])
(W/'review/floor-consistency.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
