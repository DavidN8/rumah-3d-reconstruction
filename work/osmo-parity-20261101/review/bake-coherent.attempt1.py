"""A chart-consistent photo-texturing pilot, with source masks and first-hit tests."""
from pathlib import Path
import sys,json,importlib.util,io,time,hashlib
import numpy as np
from PIL import Image
W=Path(__file__).resolve().parent;ROOT=W.parent.parent;OUT=W/'tsdf-pilot';sys.path[:0]=[str(W.parent/'tsdfdeps'),str(ROOT/'osmo-improve-20261031/pydeps'),str(ROOT/'osmo-reconstruct-20261031')]
import cv2
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
spec=importlib.util.spec_from_file_location('baker',OUT/'photo-bake-implementation.py');b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
if (OUT/'coherent-uncompressed.glb').exists():raise FileExistsError('Preserve the prior pilot')
started=time.monotonic();mesh=OUT/'surface-uncompressed.glb';raw,g,binary=b.load_glb(mesh);xyz,normals,uv,indices,image_idx,native=b.mesh_data(g,binary);faces=indices.reshape(-1,3);n=len(xyz);rows=np.concatenate([faces[:,0],faces[:,1],faces[:,2]]);cols=np.concatenate([faces[:,1],faces[:,2],faces[:,0]])
count,labels=connected_components(coo_matrix((np.ones(len(rows),'u1'),(rows,cols)),shape=(n,n)),directed=False);labels=labels.astype('i4')+1;S=4096;chart_map=np.zeros((S,S),'i4');coords=np.rint(uv*S-.5).astype('i4')
for face in faces:cv2.fillConvexPoly(chart_map,coords[face],int(labels[face[0]]))
print('UV connected charts',count,flush=True)
original=b.COMPUTE
b.COMPUTE=original.replace('uniform sampler2D photo,mask_img,depth_img,native_atlas;','uniform sampler2D photo,mask_img,depth_img,native_atlas;\nuniform usampler2D chart_ids,chart_sources;uniform bool chartConsistent;')
b.COMPUTE=b.COMPUTE.replace('float score=cosine*cosine*lens*lens/(.16+range*range);','''float score=cosine*cosine*lens*lens/(.16+range*range);
 if(chartConsistent){uint chart=texelFetch(chart_ids,ij,0).r;int rank=-1;
  for(int k=0;k<4;k++){if(int(texelFetch(chart_sources,ivec2(k,int(chart)),0).r)==view_id){rank=k;break;}}
  if(rank<0)return;score+=float(4-rank)*10000.0;
 }''')
baker=b.Baker(xyz,normals,uv,indices,S,1024,native,.75);ctx=baker.ctx;chart_tex=ctx.texture((S,S),1,chart_map.astype('u4').tobytes(),dtype='u4');chart_tex.use(8);baker.compute['chart_ids'].value=8;baker.compute['chart_sources'].value=9;baker.compute['chartConsistent'].value=False
dummy=ctx.texture((4,count+1),1,np.zeros((count+1,4),'u4').tobytes(),dtype='u4');dummy.use(9)
native_ds=Path('C:/Users/bombe/OneDrive/Documents/ChatGPT/Ruang Kamare/roomscan-reconstruction/data/20261031_OSMO360/clean-v3/dataset');cameras,images,_=b.read_model(native_ds/'sparse/0');selection=json.loads((W.parent/'frame-selection.json').read_text())['selected'];by_name={r['filename']:r for r in selection};views=sorted([im for im in images.values() if by_name[Path(im['name']).name]['split']=='train'],key=lambda im:(by_name[Path(im['name']).name]['time_seconds'],im['name']))
sources=[]
for phase in [0,1]:
    for j,im in enumerate(views,1):
        rgb=np.asarray(Image.open(native_ds/'images'/im['name']).convert('RGB'));mask=np.asarray(Image.open(b.find_mask(native_ds/'masks',im['name'])).convert('L'));mask=cv2.erode(mask,np.ones((17,17),'u1'));camera=cameras[im['camera_id']];fish=b.Fisheye(camera,width=rgb.shape[1],height=rgb.shape[0]);params=np.r_[fish.fx,fish.fy,fish.cx,fish.cy,fish.k]
        baker.add_view(b.qvec_to_rotmat(im['qvec']),im['tvec'],params,rgb,mask,j,abs_tol=.025,rel_tol=.006,phase=2)
        if j%80==0:print('Coherent texture pass',phase+1,j,'/',len(views),round(time.monotonic()-started,1),'s',flush=True)
    pos,best,choice=baker.result()
    if phase==0:
        occupied=pos[...,3]>.5;supported=occupied&(best[...,3]>0)&(chart_map>0);keys=chart_map[supported].astype('i8')*(len(views)+1)+choice[supported];votes=np.bincount(keys,minlength=(count+1)*(len(views)+1)).reshape(count+1,len(views)+1);votes[:,0]=0
        top=np.argsort(votes,axis=1)[:,-4:][:,::-1].astype('u4');chosen_votes=np.take_along_axis(votes,top,axis=1);top[chosen_votes==0]=0
        candidates=ctx.texture((4,count+1),1,top.tobytes(),dtype='u4');candidates.use(9);baker.compute['chartConsistent'].value=True;baker.best.write(bytes(S*S*16));baker.choice.write(bytes(S*S*4))
        (OUT/'chart-view-selection.json').write_text(json.dumps({'charts':count,'sourceImages':len(views),'selectedTopFourByUnmaskedVisibilityVotes':top.tolist(),'selection':'One primary camera per connected UV chart; ranked fallback only where the primary is masked or occluded. No temporal colour consensus on fine texture. Original masks and first-hit tests remain mandatory.'},indent=2))
occupied=pos[...,3]>.5;supported=occupied&(best[...,3]>0);output=np.array(native.resize((S,S),Image.Resampling.LANCZOS));output[supported]=np.clip(best[supported,:3]*255+.5,0,255).astype('u1')
distance,lut=cv2.distanceTransformWithLabels((~occupied).astype('u1'),cv2.DIST_L2,5,labelType=cv2.DIST_LABEL_PIXEL);colors=np.zeros((int(lut.max())+1,3),'u1');colors[lut[occupied]]=output[occupied];gutter=(~occupied)&(distance<=4);output[gutter]=colors[lut[gutter]]
encoded=io.BytesIO();Image.fromarray(output).save(encoded,format='JPEG',quality=92,subsampling=0,optimize=True);target=OUT/'coherent-uncompressed.glb';b.write_glb(g,binary,image_idx,encoded.getvalue(),target)
report={'surface':'Validated depth TSDF, no Gaussian mesh extraction','textureMethod':'Chart-consistent source-view assignment with ranked visibility fallback; explicit original binary masks; no colour averaging or sharpening','views':len(views),'evalImagesExcluded':True,'charts':count,'occupiedTexels':int(occupied.sum()),'supportedTexels':int(supported.sum()),'supportedFraction':float(supported.sum()/occupied.sum()),'textureSize':S,'jpegBytes':len(encoded.getvalue()),'sourceMeshSha256':hashlib.sha256(raw).hexdigest(),'sourceMeshModified':False,'seconds':time.monotonic()-started,'status':'pilot_requires_visual_review'}
(OUT/'coherent-report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
