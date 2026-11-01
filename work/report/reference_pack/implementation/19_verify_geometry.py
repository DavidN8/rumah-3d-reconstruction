"""Independent numerical checks and an XZ/XY/ZY plot of the written GLB."""
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from reconstruction_frame import BASE,read_glb,accessor,apply_sim
from colmap_io import read_model,qvec_to_rotmat


def main():
    doc,blob=read_glb(BASE/'exports/iphone-full-room.glb')
    trans=json.loads((BASE/'analysis/fixed-transforms.json').read_text())
    floor=json.loads((BASE/'analysis/floor-measurements.json').read_text())['floors']
    meta=json.loads((BASE/'exports/cameras.json').read_text())
    _,oldcams,_=read_model(BASE/'backups/before-fix-20261027/merged/sparse/0')
    oldcams={c['name']:c for c in oldcams.values()}
    colors=['#db9367','#73b4c9','#a29bd9'];labels=['Kitchen','Living + corridor','Bedroom']
    fig=plt.figure(figsize=(17,11),facecolor='#111923');grid=fig.add_gridspec(2,2,hspace=.30,wspace=.20)
    axes=[fig.add_subplot(grid[0,:]),fig.add_subplot(grid[1,0]),fig.add_subplot(grid[1,1])]
    for ax in axes:
        ax.set_facecolor('#17222e');ax.tick_params(colors='#c0d1df');ax.xaxis.label.set_color('#c0d1df');ax.yaxis.label.set_color('#c0d1df')
        for sp in ax.spines.values():sp.set_color('#536474')
        ax.grid(color='#516170',alpha=.18)
    report={'zones':[],'projection_error_pixels_max':0.,'proper_rotations':True,'nodes_have_no_frame_wrappers':True}
    for z,mesh in enumerate(doc['meshes']):
        positions=[];faces=[];offset=0
        for prim in mesh['primitives']:
            pp=accessor(doc,blob,prim['attributes']['POSITION']);ff=accessor(doc,blob,prim['indices']).reshape(-1,3)
            positions.append(pp);faces.append(ff+offset);offset+=len(pp)
        p=np.concatenate(positions);f=np.concatenate(faces)
        rec=trans['zones'][f'zone-{z}'];r=np.array(rec['R']);n=np.array(floor[z]['normal']);h=floor[z]['offset']
        mapped_up=r@n;mapped_origin=apply_sim((n*h)[None],rec)[0]
        assert np.allclose(mapped_up,[0,1,0],atol=1e-7);assert abs(mapped_origin[1])<1e-7
        assert abs(np.linalg.det(r)-1)<1e-8
        assert np.isfinite(p).all() and int(f.max())<len(p)
        cam=[c for c in meta['cameras'] if c['zone']==f'zone-{z}'];cc=np.array([c['position'] for c in cam])
        # Check projection invariance at real mesh vertices using independently
        # reconstructed old coordinates and the serialized exported cameras.
        max_error=0.
        for c in cam[::max(1,len(cam)//8)]:
            orig=oldcams[c['name']];rr=qvec_to_rotmat(orig['qvec']);sample=p[::max(1,len(p)//3000)].astype(float)
            native=(sample-np.array(rec['t']))@r/rec['scale']
            old=native@rr.T+orig['tvec'];new=sample@np.array(c['R_world_to_opencv']).T+np.array(c['t_world_to_opencv'])
            good=(old[:,2]>.03)&(new[:,2]>.03)
            error=np.max(np.linalg.norm(old[good,:2]/old[good,2,None]-new[good,:2]/new[good,2,None],axis=1))*875
            max_error=max(max_error,float(error))
        report['projection_error_pixels_max']=max(report['projection_error_pixels_max'],max_error)
        sample=p[::max(1,len(p)//70000)]
        pairs=[(0,2),(0,1),(2,1)]
        for ax,(a,b) in zip(axes,pairs):
            ax.scatter(sample[:,a],sample[:,b],s=.11,c=colors[z],alpha=.23,rasterized=True)
            ax.plot(cc[:,a],cc[:,b],color=colors[z],lw=1.5,label=labels[z])
        ceil=floor[z]['ceiling'];nc=np.array(ceil['normal']);hc=ceil['offset']
        # Ceiling height at the zone's mean floor footprint, accounting for
        # different plane normals instead of subtracting unrelated offsets.
        native_cc=np.array([-qvec_to_rotmat(oldcams[c['name']]['qvec']).T@oldcams[c['name']]['tvec'] for c in cam])
        mean=native_cc.mean(0);at_floor=mean-n*(mean@n-h)
        ceiling_height=(hc-at_floor@nc)/(n@nc)*rec['scale']
        report['zones'].append({'zone':f'zone-{z}','triangles':len(f),'vertices':len(p),
            'rotation_determinant':float(np.linalg.det(r)),'fitted_floor_Y':float(mapped_origin[1]),
            'floor_fit_rms_metres':floor[z]['rms_units']*rec['scale'],
            'dominant_upper_plane_height_metres_at_mean_footprint':float(ceiling_height),
            'upper_shell_Y_p99_metres':float(np.percentile(p[:,1],99)),
            'camera_height_metres_p10_p50_p90':np.percentile(cc[:,1],[10,50,90]).tolist(),
            'projection_invariance_error_pixels':max_error})
    assert report['projection_error_pixels_max']<1e-6
    for node in doc['nodes']:assert set(node)<=set(['mesh','name'])
    for ax in axes[1:]:
        ax.axhline(0,color='#a4efcc',lw=1.4,label='Fitted floor Y = 0');ax.set_ylim(-.25,3.5)
    axes[0].set(xlabel='X · metres (approx.)',ylabel='Z · metres (approx.)',title='TOP-DOWN FLOORPLAN · mesh + recorded camera paths')
    axes[1].set(xlabel='X · metres (approx.)',ylabel='Y · metres (approx.)',title='SIDE ELEVATION · +Y points up')
    axes[2].set(xlabel='Z · metres (approx.)',ylabel='Y · metres (approx.)',title='LONG ELEVATION · +Y points up')
    for ax in axes:ax.title.set_color('#e8f0f8');ax.set_aspect('equal',adjustable='box')
    axes[0].legend(facecolor='#17222e',labelcolor='#d8e6ef',loc='upper left')
    bridge=trans['kitchen_bridge'];heights=bridge['seam_camera_heights_metres']
    fig.suptitle('Upright apartment · baked proper rotations · measured tiled floors aligned at Y = 0',color='#e8f0f8',fontsize=16,y=.97)
    fig.text(.08,.025,f"Kitchen / living seam camera height: {heights[0]:.3f} / {heights[1]:.3f} m  ·  "
                       f"Depth-point residual median / P90: {bridge['surface_residual_metres_median']*100:.1f} / {bridge['surface_residual_metres_p90']*100:.1f} cm\n"
                       'Absolute scale uses a stated 1.50 m living camera height. Depth-derived seam alignment is an estimate; holes and moving-object ghosts remain.',
             color='#aebfce',fontsize=10)
    fig.savefig(BASE/'analysis/fixed-elevation-and-floorplan.png',dpi=150,facecolor=fig.get_facecolor(),bbox_inches='tight');plt.close(fig)
    report['triangles']=sum(x['triangles'] for x in report['zones']);report['file_bytes']=(BASE/'exports/iphone-full-room.glb').stat().st_size
    report['size_and_triangle_gate']=600000<=report['triangles']<=2000000 and report['file_bytes']<120000000
    report['visual_quality_gate']='Not claimed: recorded views still expose holes and transient-object geometry.'
    (BASE/'analysis/fixed-geometry-check.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
