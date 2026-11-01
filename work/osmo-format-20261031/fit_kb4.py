from pathlib import Path
import json,math
import numpy as np
here=Path(__file__).parent
cal=json.loads((here/'calibration.json').read_text())
base='C:/Users/bombe/OneDrive/Documents/ChatGPT/Ruang Kamare/roomscan-reconstruction/data/20261031_OSMO360'
report={'resolution':[1920,1920],'method':'Least squares fit theta_d on theta,theta^3,...theta^9 with focal free; native LensCalibration.h equivalent, sampled 4001 points. Dense 100001-angle validation. Native-refine slots1/2.','fits':[]}
cameras=[]
for lens in range(2):
    c=cal['slots'][str(lens+1)];k=np.array([c[f'k{i}'] for i in range(1,6)])
    fx,fy,cx,cy=[c[n]/2 for n in ['fx','fy','cx','cy']]
    edge=min(cx,cy,1919-cx,1919-cy)/fx
    def td(t):return t*(1+sum(k[i]*t**(2*i+2) for i in range(5)))
    lo=0.;hi=110*math.pi/180
    for _ in range(70):
        mid=(lo+hi)/2
        if td(mid)<edge:lo=mid
        else:hi=mid
    theta=np.linspace(0,lo,4001)
    A=np.column_stack([theta**(2*i+1) for i in range(5)])
    a=np.linalg.lstsq(A,td(theta),rcond=None)[0]
    scale=float(a[0]);coeff=(a[1:]/scale).tolist()
    test=np.linspace(0,lo,100001)
    pred=sum(a[i]*test**(2*i+1) for i in range(5))
    errors=fx*np.abs(pred-td(test))
    params=[fx*scale,fy*scale,cx,cy]+coeff
    thin=[fx*scale,fy*scale,cx,cy,coeff[0],coeff[1],c['p'][0]/scale,c['p'][1]/scale,coeff[2],coeff[3],0,0]
    entry={'lens':lens,'theta_max_degrees':math.degrees(lo),'circle_radius_px':edge*fx,'max_radial_error_px':float(errors.max()),'rms_radial_error_px':float(np.sqrt(np.mean(errors**2))),'opencv_fisheye_params':params,'thin_prism_fisheye_params':thin,'tangential_p_native':c['p'],'note':'Reported error is radial only; OPENCV_FISHEYE omits the small native tangential p terms. THIN_PRISM_FISHEYE params preserve them.'}
    report['fits'].append(entry)
    cameras.append({'prefix':f'cam{lens}','model':'opencv-fisheye','params':params})
q=cal['slots']['1']['cam_extri_q'];q=np.array([q.get(str(i),0) for i in range(1,5)],float);q/=np.linalg.norm(q);q[1:]*=-1
manifest={'image_dir':base+'/dataset/images','camera_mode':'folder','cameras':cameras,'rigs':[{'name':'osmo360ii-factory','kind':'dual-fisheye','members':[{'prefix':'cam0','rotation':[1,0,0,0],'translation':[0,0,0],'fixed':True},{'prefix':'cam1','rotation':q.tolist(),'translation':[0,0,0],'fixed':False,'refine':'axial'}]}]}
report['rig_note']='Rig frame is cam0: cam1 rotation = factory cam1_from_body * inverse(cam0_from_body). No factory baseline found; starts zero, axial refinement allowed. This does not establish physical scale.'
(here/'kb4-fit-report.json').write_text(json.dumps(report,indent=2))
(here/'sfm-manifest.json').write_text(json.dumps(manifest,indent=2))
print(json.dumps(report,indent=2));print(json.dumps(manifest,indent=2))
