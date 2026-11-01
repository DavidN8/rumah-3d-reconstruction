"""Conservative completion of the observed, static switch wall at the seam.

The plane is an inference from metric depth and normals, textured by a real
recorded frame. It does not create unseen appliances, furniture or door trim.
"""
import hashlib
from pathlib import Path
import cv2
import numpy as np
from reconstruction_frame import BASE,apply_sim
from colmap_io import qvec_to_rotmat


def build_switch_wall(transforms,cameras,images):
    dense=np.load(BASE/'analysis/bridge-dense.npz')
    _,idx=np.unique(dense['uv1'],axis=0,return_index=True)
    rec=transforms['zones']['zone-1'];p=apply_sim(dense['dst'][idx],rec);center=p.mean(0)
    anchor=next(x for x in images.values() if x['name']=='frame_0001390.jpg')
    normals=cv2.imread(str(BASE/'zones/dataset-unified/normals/frame_0001390.png'),-1)[:,:,::-1].astype(float)/127.5-1
    uv=dense['uv1'][idx]*[normals.shape[1]/1080,normals.shape[0]/1920]
    cam_normal=np.median(normals[uv[:,1].astype(int),uv[:,0].astype(int)],axis=0)
    world_rotation=qvec_to_rotmat(anchor['qvec'])@np.array(rec['R']).T
    n=cam_normal@world_rotation;n[1]=0;n/=np.linalg.norm(n)
    tangent=np.cross([0.,1.,0],n)
    source=next(x for x in images.values() if x['name']=='frame_0001398.jpg')
    old=qvec_to_rotmat(source['qvec']);rot=old@np.array(rec['R']).T
    position=apply_sim((-old.T@source['tvec'])[None],rec)[0]
    camera=cameras[source['camera_id']];fx,fy,cx,cy=camera['params'][:4]
    k=np.array([[fx,0,cx],[0,fy,cy],[0,0,1.]])
    xy=cv2.undistortPoints(np.array([[[0.,cy]],[[437.,cy]]]),k,camera['params'][4:8]).reshape(-1,2)
    rays=np.c_[xy,np.ones(2)]@rot
    points=position+((center-position)@n/(rays@n))[:,None]*rays
    limits=np.sort((points-center)@tangent)
    # Subdivision keeps the photographic projection accurate across the plane.
    ss,yy=np.meshgrid(np.linspace(limits[0],limits[1],13),np.linspace(0.,2.40,49))
    vertices=center+ss.ravel()[:,None]*tangent;vertices[:,1]=yy.ravel()
    xc=(vertices-position)@rot.T
    projected=cv2.projectPoints(xc,np.zeros(3),np.zeros(3),k,camera['params'][4:8])[0].reshape(-1,2)
    uv=np.clip(projected/[camera['width'],camera['height']],0,1)
    faces=[]
    for row in range(48):
        for col in range(12):
            a=row*13+col;b=a+1;c=a+13;d=c+1
            faces.extend([[a,b,d],[a,d,c]])
    image=BASE/'frames/frame_0001398.jpg';payload=image.read_bytes()
    return {'vertices':vertices.astype('<f4'),'uv':uv.astype('<f4'),
            'normals':np.repeat(n[None],len(vertices),axis=0).astype('<f4'),
            'faces':np.array(faces,dtype='<u4'),'payload':payload,
            'normal':n,'center':center,'tangent':tangent,'limits':limits,
            'report':{'method':'Observed switch-wall completion: vertical plane from metric doorway points and MoGe normals; source-frame texture projection',
                      'source_frame':image.name,'source_sha256':hashlib.sha256(payload).hexdigest(),
                      'inferred_geometry':True,'width_metres':float(limits[1]-limits[0]),'height_metres':2.40,
                      'triangles':len(faces),'limitations':'Local planar seam completion. The plane and its extrapolation beyond the photo crop are inferred, not surveyed.'}}


def replacement_mask(vertices,faces,repair):
    tri=vertices[faces];relative=tri-repair['center'];distance=relative@repair['normal'];along=relative@repair['tangent'];y=tri[:,:,1]
    cross=np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]);normal=cross/np.maximum(np.linalg.norm(cross,axis=1)[:,None],1e-12)
    return ((distance.min(1)<.22)&(distance.max(1)>-.22)&
            (along.max(1)>repair['limits'][0]-.015)&(along.min(1)<repair['limits'][1]+.015)&
            (y.max(1)>.02)&(y.min(1)<2.42)&(np.abs(normal@repair['normal'])>.40))
