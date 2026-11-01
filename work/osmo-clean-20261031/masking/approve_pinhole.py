from pathlib import Path
import json,cv2,numpy as np,shutil
from build_masks import write_json
from repair_pinhole import fast_unwarp
HERE=Path(__file__).resolve().parent
REJECT={1731,1737,1749,1770,1776,1800,1824,1860,1869,1872,1881,1890,1896}
MANUAL={
1716:[[280,0],[635,0],[615,52],[460,88],[446,200],[450,251],[469,310],[475,391],[458,446],[431,468],[397,478],[395,511],[361,549],[355,578],[363,599],[350,623],[361,672],[358,699],[348,724],[315,733],[290,733]],
1755:[[320,615],[339,672],[361,731],[382,787],[409,819],[390,851],[359,886],[336,923],[300,951],[280,951]],
1815:[[294,73],[339,82],[330,137],[322,205],[326,265],[326,420],[344,543],[349,640],[379,697],[398,760],[426,813],[414,850],[384,892],[350,930],[351,1000],[341,1024],[285,1024]],
1938:[[546,0],[639,0],[635,150],[621,220],[618,280],[626,370],[623,428],[618,476],[644,503],[644,524],[627,540],[600,526],[570,500],[549,506],[533,563],[516,603],[493,628],[455,633],[238,604]],
1944:[[546,0],[661,0],[641,77],[636,177],[625,235],[618,284],[622,350],[615,385],[622,424],[620,447],[623,479],[613,501],[595,492],[583,483],[585,520],[592,550],[589,574],[565,578],[548,566],[540,546],[528,565],[518,599],[488,627],[450,629],[238,603]],
1950:[[547,0],[658,0],[646,58],[621,109],[604,200],[600,300],[588,365],[579,394],[581,418],[581,446],[574,451],[580,491],[582,519],[584,538],[573,547],[558,544],[534,531],[522,559],[509,581],[489,597],[448,600],[253,592]]
}
audit=json.loads((HERE/'pinhole-repairs/audit.json').read_text()); changed=[]
for row in audit['frames']:
 cam=row['camera'];n=row['source_frame'];job=HERE/'pinhole-repairs'/cam/str(n);out=HERE/'operator-additions'/cam/Path(row['filename']).with_suffix('.png');out.parent.mkdir(parents=True,exist_ok=True)
 if cam=='cam0' and n in REJECT:
  row.update(approved=False,decision='Rejected static water bottle, furniture or floor-clothing detection. Existing native operator remains.')
  continue
 mask=cv2.imread(str(job/'selected-keep.png'),0);original=mask.copy();g=HERE.parent/'geometry/mask-targets'/cam/str(n);meta=json.loads((g/'view.json').read_text());valid=cv2.imread(str(g/'valid.png'),0)
 if cam=='cam0' and n in MANUAL:
  mask[:]=255;cv2.fillPoly(mask,[np.array(MANUAL[n],np.int32)],0);row['manual_view_operator_polygon']=MANUAL[n]
 if cam=='cam0' and n==1485:
  mask[775:,360:]=255;mask[835:,:]=255;row['static_mat_restoration']='x>=360,y>=775 and y>=835 in1024 view'
 if cam=='cam0' and n==1491:
  mask[670:,360:]=255;mask[950:,:]=255;row['static_mat_restoration']='x>=360,y>=670 and y>=950 in1024 view'
 if not np.array_equal(mask,original):
  cv2.imwrite(str(job/'approved-keep.png'),mask);native=fast_unwarp(mask,valid,meta);cv2.imwrite(str(out),native)
 else:shutil.copy2(job/'candidate-native-excluded.png',out)
 # Every approved addition receives a reviewable perspective overlay and native layer.
 rgb=cv2.imread(str(g/'view.png'));ex=(mask<128)&(valid>127);rgb[ex]=.45*rgb[ex]+.55*np.array([10,30,255]);cv2.imwrite(str(job/'approved-overlay.jpg'),rgb)
 row.update(approved=True,decision='Viewed source and rectified silhouette; retain actual operator, reject static scene',native_addition_file=str(out),native_exclusion_fraction=float((cv2.imread(str(out),0)>127).mean()))
 changed.append((cam,n))
audit['stage']='All candidates visually reviewed; accepted corrections separated from static-scene rejections';write_json(HERE/'pinhole-repairs/approved-audit.json',audit)
print('Approved',len(changed),'targeted additions',flush=True)
