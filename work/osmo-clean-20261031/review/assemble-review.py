"""CPU-only plate assembly and pixel comparison for browser-saved exact-pose renders."""
from pathlib import Path
import json, shutil, sys, math
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent.parent/'osmo-improve-20261031/pydeps'))
import numpy as np
from PIL import Image, ImageDraw, ImageFont

cameras=json.loads((HERE.parent.parent/'mobile-20261029/legacy-osmo-cameras.json').read_text())
renders=HERE/'renders';renders.mkdir(exist_ok=True)
for kind in ('native','mesh','compressed','sog'):
    for i in range(1,7):
        name=f'{kind}-pose-{i}.png'
        shutil.copy2(Path.home()/'Downloads'/name,renders/name)
font=ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf',22)
small=ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf',17)
sheet=Image.new('RGB',(1800,6*675),(21,27,34))
metrics=[]
for i,pre in enumerate(cameras['presets'],1):
    source=Image.open(pre['sourceFile']).convert('RGB').resize((600,600),Image.Resampling.LANCZOS)
    native=Image.open(renders/f'native-pose-{i}.png').convert('RGB')
    mesh=Image.open(renders/f'mesh-pose-{i}.png').convert('RGB')
    compressed=Image.open(renders/f'compressed-pose-{i}.png').convert('RGB')
    maskfile=Path(pre['sourceFile']).with_name(Path(pre['sourceFile']).stem+'-valid.png')
    mask=np.asarray(Image.open(maskfile).convert('L').resize((600,600),Image.Resampling.NEAREST))>127
    source_array=np.asarray(source,dtype=float)
    out={'view':pre['name'],'camera':pre,'valid_source_fraction':float(mask.mean())}
    for name,im in [('native',native),('mesh',mesh),('compressed',compressed)]:
        array=np.asarray(im,dtype=float);delta=(array-source_array)[mask]
        out[name]={'source_valid_rgb_mae_255':float(np.mean(np.abs(delta))),'source_valid_rgb_rmse_255':float(np.sqrt(np.mean(delta*delta))),'near_black_fraction_in_source_valid_pixels':float((np.max(array,axis=-1)[mask]<3).mean())}
    delta=np.asarray(native,dtype=float)-np.asarray(compressed,dtype=float)
    rmse=float(np.sqrt(np.mean(delta*delta)))
    out['spz_vs_ply']={'all_pixel_rgb_rmse_255':rmse,'all_pixel_rgb_mae_255':float(np.abs(delta).mean()),'psnr_db':20*math.log10(255/max(rmse,1e-9))}
    sog=Image.open(renders/f'sog-pose-{i}.png').convert('RGB')
    delta=np.asarray(native,dtype=float)-np.asarray(sog,dtype=float);rmse=float(np.sqrt(np.mean(delta*delta)))
    out['sog_vs_ply']={'all_pixel_rgb_rmse_255':rmse,'all_pixel_rgb_mae_255':float(np.abs(delta).mean()),'psnr_db':20*math.log10(255/max(rmse,1e-9))}
    metrics.append(out)
    plate=Image.new('RGB',(1800,675),(21,27,34));draw=ImageDraw.Draw(plate)
    for j,(title,im) in enumerate([('Calibrated source photograph',source),('Original native Gaussian PLY',native),('Published triangle mesh GLB',mesh)]):
        draw.text((j*600+12,8),title,font=font,fill='white');draw.text((j*600+12,40),pre['label'],font=small,fill='#bac7d6');plate.paste(im,(j*600,75))
    plate.save(renders/f'matched-pose-{i}.jpg',quality=94,subsampling=0)
    sheet.paste(plate,(0,(i-1)*675))
sheet.save(renders/'six-view-source-native-mesh.jpg',quality=94,subsampling=0)
report={'scope':'Six training-geometry camera poses, not held-out geometry validation. Source is calibrated/masked virtual pinhole reprojected from fisheye, not native pinhole photo. Black metric is a display proxy; not geometric completeness. All screenshots 600x600, no lighting/ceiling clipping, matched projection. Original PLY and SPZ render through Spark 2.4.0, not a claim of bit-identical Spirula backend.', 'renderer':'Three 0.180.0 and Spark 2.4.0; 3D mip splats, sortRadial false, LoD false, extSplats true, blurAmount .3, preBlurAmount 0; all 2,997,515 splats','spz_file_bytes':48377598,'cameras':metrics}
(HERE/'matched-review.json').write_text(json.dumps(report,indent=2))
print(json.dumps({'plates':6,'composite':str(renders/'six-view-source-native-mesh.jpg'),'spz_vs_ply_psnr_db':[round(m['spz_vs_ply']['psnr_db'],2) for m in metrics],'sog_vs_ply_psnr_db':[round(m['sog_vs_ply']['psnr_db'],2) for m in metrics],'mean_source_rmse_255':{kind:round(sum(m[kind]['source_valid_rgb_rmse_255'] for m in metrics)/6,2) for kind in ('native','mesh','compressed')}},indent=2))
