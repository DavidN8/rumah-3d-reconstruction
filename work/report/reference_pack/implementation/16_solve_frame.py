"""Solve an upright frame and a floor-constrained, surface-backed kitchen join.

Checkpoint datasets stay immutable. All output transforms map their existing
shared training frame into the one final, metre-scale, +Y-up export frame.
"""
import json
from pathlib import Path
import numpy as np
import cv2
from numba import njit
from scipy.optimize import least_squares
from scipy.spatial.transform import Rotation
from colmap_io import read_model,qvec_to_rotmat
from reconstruction_frame import BASE,proper_rotation,mesh_arrays


@njit(cache=False)
def intersect_rays(origins,directions,vertices,triangles):
    result=np.full((len(origins),3),np.nan)
    for k in range(len(origins)):
        o=origins[k];d=directions[k];best=1e30
        for tr in triangles:
            a,b,c=vertices[tr[0]],vertices[tr[1]],vertices[tr[2]]
            e1,e2=b-a,c-a;p=np.cross(d,e2);det=np.dot(e1,p)
            if abs(det)<1e-12:continue
            inv=1/det;v=o-a;u=np.dot(v,p)*inv
            if u<0 or u>1:continue
            q=np.cross(v,e1);vv=np.dot(d,q)*inv
            if vv<0 or u+vv>1:continue
            t=np.dot(e2,q)*inv
            if .008<t<best:best=t
        if best<1e29:result[k]=o+best*d
    return result


def main():
    measurements=json.loads((BASE/'analysis/floor-measurements.json').read_text())
    floors=measurements['floors'];ups=np.array(measurements['camera_up'])
    cams,images,_=read_model(BASE/'backups/before-fix-20261027/merged/sparse/0')
    ims=sorted(images.values(),key=lambda x:x['name'])
    def zone(n):return 0 if n<=1388 else 1 if n<=4090 else 2
    def src(im):return int(Path(im['name']).stem.split('_')[-1])
    centres={im['name']:-qvec_to_rotmat(im['qvec']).T@im['tvec'] for im in ims}
    n0,n1=[np.array(floors[z]['normal']) for z in (0,1)]
    h0,h1=[floors[z]['offset'] for z in (0,1)]
    e1=np.array([1.,0,0]);e1-=n1*(e1@n1);e1/=np.linalg.norm(e1);e2=np.cross(n1,e1)
    level=proper_rotation(n0,n1)
    ca=np.array([centres[im['name']] for im in ims if zone(src(im))==0][-4:])
    cb=np.array([centres[im['name']] for im in ims if zone(src(im))==1][:4])
    ha=np.median(ca@n0-h0);hb=np.median(cb@n1-h1);scale_height=hb/ha
    dense=np.load(BASE/'analysis/bridge-dense.npz')
    # The accepted dense pair is the adjacent source pair 1386/1390. Deduplicate.
    ua,idx=np.unique(dense['uv0'],axis=0,return_index=True);ub=dense['uv1'][idx]
    old=json.loads((BASE/'backups/before-fix-20261027/model-merge.json').read_text())['similarity']
    # The white switch wall is partly absent in the extracted mesh. Use matched
    # MoGe 3D points, tied to each independent SfM component by observed sparse
    # depths, instead of intersecting rays with a farther wall through a hole.
    pa=old['scale']*dense['src'][idx]@np.array(old['R']).T+np.array(old['t'])
    pb=dense['dst'][idx]
    good=np.isfinite(pa[:,0])&np.isfinite(pb[:,0]);pa,pb=pa[good],pb[good]
    assert len(pa)>=8,'Insufficient depth-backed doorway matches'
    start_t=cb[0]-scale_height*level@ca[-1]
    def unpack(x):
        s=np.exp(x[0]);r=Rotation.from_rotvec(n1*x[1]).as_matrix()@level
        t=e1*x[2]+e2*x[3]+n1*(h1-s*h0)
        return s,r,t
    def residual(x):
        s,r,t=unpack(x)
        # Surface residuals have centimetre-level precision; seam camera height
        # is a physical constraint independent of learned metric depth.
        surface=(s*pa@r.T+t-pb).ravel()
        height=np.array([(s*ha-hb)*6.])
        return np.r_[surface,height]
    initial=[np.log(scale_height),0.,start_t@e1,start_t@e2]
    solution=least_squares(residual,initial,loss='soft_l1',f_scale=.006,
                           bounds=([np.log(.3),-.22,-4,-4],[np.log(1.5),.22,4,4]),max_nfev=500)
    sd,rd,td=unpack(solution.x)
    trial_error=np.linalg.norm(sd*pa@rd.T+td-pb,axis=1)
    rejected_surface_fit = np.median(trial_error)>.02 or abs(solution.x[1])>.21
    if rejected_surface_fit:
        # A weak planar patch must not be allowed to drag the room to a wrong
        # wall. Enforce only independently observable floor and height facts.
        sd=scale_height
        a=next(x for x in ims if x['name']=='frame_0001386.jpg')
        b=next(x for x in ims if x['name']=='frame_0001390.jpg')
        target_rotation=qvec_to_rotmat(b['qvec']).T@qvec_to_rotmat(a['qvec'])
        yaw=float(Rotation.from_matrix(target_rotation@level.T).as_rotvec()@n1)
        rd=Rotation.from_rotvec(n1*yaw).as_matrix()@level
        # Extrapolate one source interval from the first living cameras. Keep a
        # finite doorway step instead of forcing two recorded centres equal.
        living_start=[im for im in ims if zone(src(im))==1][:10]
        velocities=[(centres[v['name']]-centres[u['name']])/(src(v)-src(u))
                    for u,v in zip(living_start,living_start[1:])]
        step=np.median(velocities,axis=0)*4
        step-=n1*(step@n1)
        desired=centres[b['name']]-step
        td=desired-sd*rd@centres[a['name']]
        td+=n1*(h1-sd*h0-n1@td)
        solution.x[1]=yaw
    # Global scale is supported by fresh MoGe in living (3.96 m/u), and anchored
    # to a stated 1.50 m handheld height above the measured living floor.
    living=np.array([centres[im['name']] for im in ims if zone(src(im))==1])
    metre_scale=1.5/np.median(living@n1-h1)
    rg=proper_rotation(n1,np.array([0.,1,0]))
    allc=np.array(list(centres.values()));xz=allc@rg.T
    mid=(xz.min(0)+xz.max(0))/2
    tg=np.array([-mid[0]*metre_scale,-h1*metre_scale,-mid[2]*metre_scale])
    transforms={}
    for z in range(3):
        if z==0:
            s,r,t=sd,rd,td
        elif z==2:
            # Correct the small independently measured bedroom floor drift.
            nz=np.array(floors[z]['normal']);hz=floors[z]['offset'];r=proper_rotation(nz,n1);s=1.
            cc=np.array([centres[im['name']] for im in ims if zone(src(im))==2]);pivot=cc.mean(0)
            t=pivot-r@pivot;t+=n1*(h1-hz-n1@t)
        else:s,r,t=1.,np.eye(3),np.zeros(3)
        transforms[f'zone-{z}']={'scale':float(metre_scale*s),'R':(rg@r).tolist(),
                                 't':(metre_scale*rg@t+tg).tolist(),
                                 'training_correction':{'scale':float(s),'R':r.tolist(),'t':t.tolist()}}
    residuals=np.linalg.norm(sd*pa@rd.T+td-pb,axis=1)*metre_scale
    out={'version':1,'formula':'p_gltf = scale * R @ p_training + t; normals = R @ n',
         'up_from_501_cameras':ups.tolist(),'floor_up':n1.tolist(),
         'global':{'scale':float(metre_scale),'R':rg.tolist(),'t':tg.tolist()},'zones':transforms,
         'kitchen_bridge':{'method':'GPU LoFTR / fresh metric MoGe 3D correspondences / floor-coplanar Sim3 / seam camera-height continuity',
                           'surface_fit_rejected':bool(rejected_surface_fit),
                           'precise_registration_verified':False,
                           'unique_surface_matches':len(pa),'unique_depth_matches':len(pa),'relative_scale_correction':float(sd),
                           'height_only_scale_correction':float(scale_height),
                           'surface_residual_metres_median':float(np.median(residuals)),
                           'surface_residual_metres_p90':float(np.percentile(residuals,90)),
                           'seam_camera_heights_metres':[float(sd*ha*metre_scale),float(hb*metre_scale)],
                           'yaw_correction_degrees':float(solution.x[1]*180/np.pi)},
         'metric_scale':'Approximate metres: 1.50 m median living camera height; fresh MoGe living depth cross-check. No surveyed length.',
         'limitations':['Doorway overlap is weak and mostly planar: 18 unique dense matches; sub-centimetre registration is not established.',
                       'Metric MoGe and true tiled floor heights support a roughly 0.46 correction to the previously joined kitchen; the near-zero kitchen surface is its countertop.',
                       'Bedroom receives a local floor leveling correction; original checkpoint datasets remain immutable.']}
    for rec in transforms.values():assert abs(np.linalg.det(rec['R'])-1)<1e-8
    (BASE/'analysis/fixed-transforms.json').write_text(json.dumps(out,indent=2))
    np.savez_compressed(BASE/'analysis/bridge-surface-matches.npz',kitchen=pa,living=pb,corrected=sd*pa@rd.T+td)
    print(json.dumps({k:v for k,v in out.items() if k not in ['zones']},indent=2))


if __name__=='__main__':main()
