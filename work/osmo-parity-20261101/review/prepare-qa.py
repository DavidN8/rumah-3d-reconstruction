from pathlib import Path
import json,sys,os,math
import numpy as np,cv2
W=Path(__file__).resolve().parent;ROOT=W.parent.parent;OLD=ROOT/'osmo-clean-20261031';sys.path.insert(0,str(ROOT/'osmo-reconstruct-20261031'))
from seed_fisheye import read_model,qvec_to_rotmat,rotmat_to_qvec,Fisheye
CAP=Path('C:/Users/bombe/OneDrive/Documents/ChatGPT/Ruang Kamare/roomscan-reconstruction/data/20261031_OSMO360');source=CAP/'clean-v3/dataset';cams,ims,_=read_model(source/'sparse/0')
camera_data=json.loads((OLD/'review/clean-cameras.json').read_text());out=W/'qa';out.mkdir(exist_ok=True)
models={
 'old-full':CAP/'clean-v3/explicit-full-v1/training/osmo-explicit-depth-v1/step-000050000.ckpt/splat.ply',
 'pilot-base':CAP/'parity-20261101/pilots/baseline-1200/training/baseline-1200/step-000008000.ckpt/splat.ply',
 'pilot-sharp':CAP/'parity-20261101/pilots/sharp-1600/training/sharp-1600/step-000008000.ckpt/splat.ply',
 'mesh-texture':W/'mesh-pilot/texture-preview.glb',
 'mesh-photo':W/'mesh-pilot/photo-baked.glb',
 'fusion-photo':W/'tsdf-pilot/photo-baked.glb',
 'fusion-coherent':W/'tsdf-pilot/coherent.glb',
 'fusion-filled':W/'tsdf-pilot/coherent-filled.glb',
 'poisson-photo':W/'poisson-projected/coherent-filled.glb',
}
for name in ['rgb-only-mip','rgb-only-3dgs','no-appearance-correction','sparse-rgb-only']:
    models[name]=CAP/f'parity-20261101/pilots/diagnostics/{name}/training/{name}/step-000008000.ckpt/splat.ply'
assets=json.loads((out/'metadata.json').read_text())['models'] if (out/'metadata.json').exists() else {}
for key,file in models.items():
    if not file.exists():continue
    dst=out/(key+file.suffix)
    if not dst.exists():os.link(file,dst)
    assets[key]={'url':'/review/qa/'+dst.name,'format':file.suffix[1:],'bytes':file.stat().st_size}
poses=[];WW,HH=1920,1080;f=HH/2/math.tan(math.radians(75/2));yy,xx=np.mgrid[:HH,:WW];rays=np.stack([(xx-WW/2)/f,(yy-HH/2)/f,np.ones_like(xx)],axis=-1).reshape(-1,3)
for label,index,down in [('fridge',0,.18),('fan',6,.10),('dining',4,.10),('bathroom',5,0)]:
    p=camera_data['presets'][index];q=p['quaternion'];r=qvec_to_rotmat(np.array([q[3],*q[:3]]));angle=-down;ca,sa=math.cos(angle),math.sin(angle);r=r@np.array([[1,0,0],[0,ca,-sa],[0,sa,ca]])
    Rv=np.diag([1,-1,-1])@r.T;qnew=rotmat_to_qvec(r);im=ims[p['sourceImageId']];R=qvec_to_rotmat(im['qvec']);fish=Fisheye(cams[im['camera_id']],max_theta_degrees=99);uv,valid=fish.project(rays@Rv@R.T)
    raw=cv2.imread(str(source/'images'/im['name']));mask=cv2.imread(str((source/'masks'/im['name']).with_suffix('.png')),0);mx=uv[:,0].reshape(HH,WW).astype('f4');my=uv[:,1].reshape(HH,WW).astype('f4')
    rgb=cv2.remap(raw,mx,my,cv2.INTER_LANCZOS4,borderMode=cv2.BORDER_CONSTANT);keep=valid.reshape(HH,WW)&(cv2.remap(mask,mx,my,cv2.INTER_NEAREST,borderMode=cv2.BORDER_CONSTANT)>127);rgb[~keep]=0
    cv2.imwrite(str(out/(label+'-source.png')),rgb);cv2.imwrite(str(out/(label+'-keep.png')),keep.astype('u1')*255)
    poses.append({'label':label,'source':im['name'],'sourceFrame':p['sourceFrame'],'split':p['split'],'position':p['position'],'quaternion':[*qnew[1:],qnew[0]],'fov':75,'width':WW,'height':HH,'intrinsics':[f,f,WW/2,HH/2],'mask':label+'-keep.png'})
(out/'metadata.json').write_text(json.dumps({'models':assets,'poses':poses,'sourcePhotographs':'Direct 3840 native RGB remap using audited calibration and exact camera pose; binary masks unchanged; no learned image generation'},indent=2))
print('Prepared QA models and four full-viewport source references')
