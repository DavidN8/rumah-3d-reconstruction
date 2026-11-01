"""CPU-only source-track brightness/color diagnostic; no color correction."""
import argparse,json,time
from pathlib import Path
import numpy as np
from PIL import Image
import photo_bake_agent as pb
from seed_fisheye import sample_map

DATA=Path(r'C:\Users\bombe\OneDrive\Documents\ChatGPT\Ruang Kamare\roomscan-reconstruction\data\20261031_OSMO360\lite-v1\dataset')
parser=argparse.ArgumentParser();parser.add_argument('--exclude-images',default='');parser.add_argument('--output',type=Path,default=Path(__file__).parent/'source-photometric-audit.json');parser.add_argument('--write-gains',type=Path);args=parser.parse_args()
excluded=set(args.exclude_images.split(',')) if args.exclude_images else set()
start=time.monotonic();cameras,images,points=pb.read_model(DATA/'sparse/0')
eligible={pid for pid,p in points.items() if p['track_len']>=5}
rows=[];view_names=[]
for vi,im in enumerate(sorted([im for im in images.values() if im['name'] not in excluded],key=lambda im:im['name'])):
    view_names.append(im['name']);keep=np.array([int(pid) in eligible for pid in im['point3D_ids']]);xy=im['points2D_xy'][keep];ids=im['point3D_ids'][keep]
    if not len(xy):continue
    rgb=np.asarray(Image.open(DATA/'images'/im['name']).convert('RGB'))
    mask=np.asarray(Image.open(pb.find_mask(DATA/'masks',im['name'])).convert('L'))
    color=sample_map(rgb,xy).astype('f4')/255
    # Reject high-gradient edges, clipped channels, dark noise and masked people.
    grad=np.maximum(np.max(np.abs(sample_map(rgb,xy+[1,0]).astype(float)-sample_map(rgb,xy-[1,0]).astype(float)),axis=1),np.max(np.abs(sample_map(rgb,xy+[0,1]).astype(float)-sample_map(rgb,xy-[0,1]).astype(float)),axis=1))
    valid=(sample_map(mask,xy,True).reshape(-1)>127)&(grad<35)&(color.min(1)>.07)&(color.max(1)<.97)
    ray,_=pb.Fisheye(cameras[im['camera_id']]).unproject(xy)
    theta=np.degrees(np.arctan2(np.linalg.norm(ray[:,:2],axis=1),ray[:,2]))
    linear=np.where(color<=.04045,color/12.92,((color+.055)/1.055)**2.4)
    rows.append(np.column_stack([np.full(valid.sum(),vi),ids[valid],linear[valid],theta[valid]]))
obs=np.concatenate(rows);order=np.argsort(obs[:,1]);obs=obs[order]
_,starts,counts=np.unique(obs[:,1],return_index=True,return_counts=True)
target=np.zeros((len(obs),3));usable=np.zeros(len(obs),bool)
for st,count in zip(starts,counts):
    if count<4:continue
    target[st:st+count]=np.median(obs[st:st+count,2:5],axis=0);usable[st:st+count]=True
obs=obs[usable];target=target[usable]
source_luma=obs[:,2:5]@np.array([.2126,.7152,.0722]);target_luma=target@np.array([.2126,.7152,.0722])
residual=np.log2(np.maximum(source_luma,1e-5)/np.maximum(target_luma,1e-5));rgb_res=np.log2(np.maximum(obs[:,2:5],1e-5)/np.maximum(target,1e-5))
summary=[];view_offset=np.zeros(len(view_names))
for vi,name in enumerate(view_names):
    sel=obs[:,0]==vi;vals=residual[sel]
    if len(vals)<30:continue
    offset=float(np.median(vals));view_offset[vi]=offset
    summary.append({'name':name,'observations':int(sel.sum()),'median_brightness_stops':offset,'rgb_channel_stops':np.median(rgb_res[sel],axis=0).tolist(),'residual_mad_stops':float(np.median(np.abs(vals-offset)))})
edge=[]
for lens in ['cam0','cam1']:
    inds=np.array([i for i,n in enumerate(view_names) if n.startswith(lens+'/')]);lens_sel=np.isin(obs[:,0],inds)
    for lo,hi in [(0,30),(30,60),(60,80),(80,95),(95,106)]:
        sel=lens_sel&(obs[:,5]>=lo)&(obs[:,5]<hi);v=residual[sel]-view_offset[obs[sel,0].astype(int)]
        edge.append({'lens':lens,'theta_degrees':[lo,hi],'observations':int(sel.sum()),'brightness_stops_after_view_offset':float(np.median(v)) if len(v) else None})
offsets=np.array([r['median_brightness_stops'] for r in summary]);spread=np.percentile(offsets,[5,50,95]).tolist()
fit_half=(obs[:,1].astype(int)%2)==0;test_half=~fit_half;fit_offset=np.zeros(len(view_names));fit_views=[]
for vi,name in enumerate(view_names):
    sel=fit_half&(obs[:,0]==vi)
    if sel.sum()<50:continue
    fit_offset[vi]=np.clip(np.median(residual[sel]),-.2,.2);fit_views.append(vi)
test=test_half&np.isin(obs[:,0],fit_views)
source=obs[test,2:5];truth=target[test];corrected=np.clip(source*2**(-fit_offset[obs[test,0].astype(int),None]),0,1)
def to_srgb(x):return np.where(x<=.0031308,12.92*x,1.055*x**(1/2.4)-.055)
srgb_truth=to_srgb(truth);rmse=lambda x:float(np.sqrt(np.mean((to_srgb(x)-srgb_truth)**2))*255)
crossval={'scope':'Fit one scalar linear exposure offset per view on even-ID source tracks, evaluate odd-ID tracks against per-track multi-view median. Diagnostic only; not independent photographic image validation.',
          'gain_clamp_stops':[-.2,.2],'fitted_views':len(fit_views),'evaluation_observations':int(test.sum()),'source_srgb_rmse_255':rmse(source),'scalar_corrected_srgb_rmse_255':rmse(corrected)}
result={'scope':'CPU source RGB audit of static high-track, non-clipped, low-gradient SfM observations. Brightness reference is per-track median across views; no correction applied. Specularity, correspondence uncertainty and vignette/scene correlations can remain.',
        'observations':len(obs),'accepted_point_tracks':int(np.unique(obs[:,1]).size),'view_median_stops_p05_p50_p95':spread,
        'p05_to_p95_exposure_ratio':float(2**(spread[2]-spread[0])),'lens_radial_bins':edge,'half_track_exposure_crosscheck':crossval,'views':summary,'seconds':time.monotonic()-start}
result['excluded_source_views']=sorted(excluded)
args.output.write_text(json.dumps(result,indent=2))
if args.write_gains:
    gains={name:0. for name in view_names};fitted=[]
    for row in summary:
        if row['observations']<100:continue
        gains[row['name']]=float(-np.clip(row['median_brightness_stops'],-.2,.2));fitted.append(row['name'])
    gain_report={'correction_stops_by_image':gains,'clamp_stops':[-.2,.2],'fit_basis':'Scalar linear-luminance exposure only. Median log2 brightness residual of>=100 unmasked, non-clipped, low-gradient observations in static SfM tracks per view; target is per-track median across texture-source views. No white-balance/channel fitting.',
                 'excluded_from_fit':sorted(excluded),'fitted_images':fitted,'insufficient_data_correction':'0 stops','dataset':str(DATA),'diagnostic_report':str(args.output),'crosscheck':crossval}
    args.write_gains.write_text(json.dumps(gain_report,indent=2));result['gain_output']=str(args.write_gains);result['gain_fitted_views']=len(fitted)
print(json.dumps({k:v for k,v in result.items() if k!='views'},indent=2))
