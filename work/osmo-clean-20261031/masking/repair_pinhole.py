from pathlib import Path
import sys,json,subprocess,cv2,numpy as np,time,hashlib
from PIL import Image
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'geometry'))
from operator_pinhole import camera_from_manifest,pinhole_map,unwarp_mask,Fisheye
from build_masks import DEFAULT_DATASET as DS,DEFAULT_RUNTIME as RT,write_json
GEOM=HERE.parent/'geometry';records={r['source_frame']:r for r in json.loads((HERE.parent/'frame-selection.json').read_text())['selected']}
TARGETS={'cam0':[1221,1230,1287,1299,1308,1344,1356,1374,1377,1386,1392,1401,1407,1473,1482,1485,1491,1497,1506,1584,1626,1629,1659,1668,1677,1695,1704,1716,1722,1731,1737,1749,1755,1761,1770,1776,1785,1800,1809,1815,1824,1860,1869,1872,1881,1890,1896,1926,1938,1944,1950], 'cam1':[1254,1266,1386,1497,1737,1515]}

INVERSE={}
def fast_unwarp(keep, valid, meta):
 key=(meta['camera_name'],meta['center_phi_deg'],meta['roll_deg'])
 first=key not in INVERSE
 if key not in INVERSE:
  camera=meta['camera'];model=Fisheye(camera);basis=np.asarray(meta['virtual_to_native_rotation']);size=meta['view_size'];focal=meta['focal'];cx,cy=meta['principal_point']
  lookup=np.full((3840,3840),-1,np.int32);view_indices=np.arange(size*size,dtype=np.float32).reshape(size,size)
  for start in range(0,3840,128):
   end=min(start+128,3840);yy,xx=np.mgrid[start:end,0:3840].astype(float)
   native,good=model.unproject(np.stack([xx+.5,yy+.5],axis=-1));angle=np.rad2deg(np.arctan2(np.linalg.norm(native[...,:2],axis=-1),native[...,2]));good&=angle<=meta['max_native_theta_deg']
   local=native@basis;good&=local[...,2]>1e-8;z=np.maximum(local[...,2],1e-8)
   u=(focal*local[...,0]/z+cx-.5).astype(np.float32);v=(focal*local[...,1]/z+cy-.5).astype(np.float32)
   good&=(u>=-.5)&(u<size-.5)&(v>=-.5)&(v<size-.5);u[~good]=-1;v[~good]=-1
   sampled_valid=cv2.remap(valid,u,v,cv2.INTER_NEAREST,borderMode=cv2.BORDER_CONSTANT,borderValue=0)>127
   indices=cv2.remap(view_indices,u,v,cv2.INTER_NEAREST,borderMode=cv2.BORDER_CONSTANT,borderValue=-1).astype(np.int32);indices[~(good&sampled_valid)]=-1;lookup[start:end]=indices
  INVERSE[key]=lookup
 lookup=INVERSE[key];out=np.zeros(lookup.shape,np.uint8);covered=lookup>=0;out[covered]=(keep.ravel()[lookup[covered]]<128)*255
 if first:
  reference,_=unwarp_mask(keep,valid,meta,'keep')
  if not np.array_equal(out,reference):raise RuntimeError('Cached mapping differs from calibrated reference')
  print('Calibrated inverse cache validated bit-for-bit:',key,flush=True)
 return out
def main():
 rows=[]
 for cam,ns in TARGETS.items():
  lens=int(cam[-1]); camera=camera_from_manifest(GEOM/'sfm-manifest-native3840.json',lens)
  for n in ns:
   r=records[n];job=HERE/'pinhole-repairs'/cam/str(n);job.mkdir(parents=True,exist_ok=True)
   g=GEOM/'mask-targets'/cam/str(n);g.mkdir(parents=True,exist_ok=True)
   phi=0 if cam=='cam0' else 180
   if cam=='cam0' and n>=1926:phi=65
   if cam=='cam1' and n==1515:phi=105
   roll=180 if cam=='cam0' else 0
   view=g/'view.png';validfile=g/'valid.png';metafile=g/'view.json'
   if not metafile.exists():
    mx,my,valid,meta=pinhole_map(camera,75,phi,roll,100,1024)
    rgb=cv2.imread(str(DS/'images'/cam/r['filename']));out=cv2.remap(rgb,mx,my,cv2.INTER_LINEAR);out[~valid]=0
    cv2.imwrite(str(view),out);cv2.imwrite(str(validfile),valid.astype('uint8')*255)
    meta.update(source_image=str(DS/'images'/cam/r['filename']),view_image=str(view),view_validity=str(validfile),source_frame=n,camera_name=cam)
    write_json(metafile,meta)
   if not (job/'seg_mask.png').exists():
    prompt='shirt;person' if n==1515 and cam=='cam1' else 'jeans;pants;bare feet;person'
    cmd=[str(RT/'bin/spirula.exe'),'sam','segment','--model',str(RT/'models/sam2.1_hiera_small_f16.ggml'),'--image',str(view),'--text',prompt,'--detector',str(RT/'models/gdino-tiny.safetensors'),'--detector-threshold','.28','--dilate-ratio','0','--out',str(job),'--device','auto']
    with (job/'inference.log').open('w') as log:subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,check=True)
   raw=cv2.imread(str(job/'seg_mask.png'),0)<128
   valid=cv2.imread(str(validfile),0);raw&=valid>127
   count,labels,stats,_=cv2.connectedComponentsWithStats(raw.astype('uint8'),8)
   if count<2:raise RuntimeError(f'No detection {cam} {n}')
   selected=1+np.argmax(stats[1:,cv2.CC_STAT_AREA]);ex=(labels==selected).astype('uint8')
   # Candidate only: reviewing a largest component is mandatory before merge.
   cv2.imwrite(str(job/'selected-keep.png'),(1-ex)*255)
   rgb=cv2.imread(str(view));over=rgb.copy();over[ex>0]=.45*over[ex>0]+.55*np.array([10,30,255]);cv2.imwrite(str(job/'selected-overlay.jpg'),over)
   if not (job/'candidate-native-excluded.png').exists():
    meta=json.loads(metafile.read_text());native=fast_unwarp((1-ex)*255,valid,meta);cv2.imwrite(str(job/'candidate-native-excluded.png'),native)
   rows.append({'camera':cam,'source_frame':n,'filename':r['filename'],'phi':phi,'roll':roll,'selected_component_px':int(stats[selected,cv2.CC_STAT_AREA]),'component_count':int(count-1),'approved':False})
   print(cam,n,'candidate complete',flush=True)
 write_json(HERE/'pinhole-repairs/audit.json',{'frames':rows,'stage':'candidate; manual visual approval required','native_addition_semantics':'WHITE exclude, zero no opinion'})

if __name__=='__main__':main()
