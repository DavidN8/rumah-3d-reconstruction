"""Measure real floor and ceiling planes from surface area and camera up."""
import json
import numpy as np
from colmap_io import read_model,qvec_to_rotmat
from reconstruction_frame import BASE,fit_floor,mesh_arrays


def main():
    _,ims,_=read_model(BASE/'backups/before-fix-20261027/merged/sparse/0')
    up=np.mean([qvec_to_rotmat(x['qvec']).T@np.array([0,-1,0]) for x in ims.values()],axis=0);up/=np.linalg.norm(up)
    records=[]
    for z in range(3):
        _,im,_=read_model(BASE/f'zones/zone-{z}/sparse/0')
        c=np.array([-qvec_to_rotmat(x['qvec']).T@x['tvec'] for x in im.values()])
        p,t=mesh_arrays(BASE/f'exports/optimized-m12/zone-{z}/zone-{z}.glb')
        f=fit_floor(p,t,up,c);f['zone']=z;f['ceiling']=fit_floor(p,t,up,c,True);records.append(f)
        print('zone',z,'floor',f['normal'],f['offset'],'camera height',np.median(f['camera_heights_units']),flush=True)
    (BASE/'analysis/floor-measurements.json').write_text(json.dumps({'camera_up':up.tolist(),'floors':records},indent=2))


if __name__=='__main__':main()
