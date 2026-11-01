"""Locate native evaluation faces matching one calibrated source crop.

Uses image features only to identify/export a diagnostic camera overlap. Native
renders are unaltered on disk. A labelled homography reprojection is used solely
for comparison; it does not modify the trained geometry or create reference data.
"""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import argparse,json
import cv2,numpy as np
from PIL import Image,ImageDraw
HERE=Path(__file__).resolve().parent
P=argparse.ArgumentParser();P.add_argument('--pose',type=int,default=6);a=P.parse_args();cv2.setNumThreads(1)
RUN=Path('C:/Users/bombe/OneDrive/Documents/ChatGPT/Ruang Kamare/roomscan-reconstruction/data/20261031_OSMO360/clean-v3/training/osmo-clean-normals-v1')
pose=json.loads((HERE/'clean-cameras.json').read_text())['presets'][a.pose-1];path=Path(pose['sourceFile']);source=cv2.imread(str(path));source=cv2.resize(source,(700,700),interpolation=cv2.INTER_AREA)
mask=cv2.imread(str(path.with_name(path.stem+'-valid.png')),0);mask=cv2.resize(mask,(700,700),interpolation=cv2.INTER_NEAREST)
sift=cv2.SIFT_create(nfeatures=3000);keys,desc=sift.detectAndCompute(cv2.cvtColor(source,cv2.COLOR_BGR2GRAY),mask)
def compare(target_path):
    target=cv2.imread(str(target_path));target=cv2.resize(target,(700,700),interpolation=cv2.INTER_AREA)
    tk,td=cv2.SIFT_create(nfeatures=3000).detectAndCompute(cv2.cvtColor(target,cv2.COLOR_BGR2GRAY),None)
    if td is None or len(td)<12:return None
    matches=cv2.FlannBasedMatcher(dict(algorithm=1,trees=4),dict(checks=64)).knnMatch(desc,td,k=2)
    good=[m for m,n in matches if m.distance<.7*n.distance]
    if len(good)<12:return None
    p=np.float32([keys[m.queryIdx].pt for m in good]);q=np.float32([tk[m.trainIdx].pt for m in good]);H,inlier=cv2.findHomography(p,q,cv2.RANSAC,1.5)
    if H is None:return None
    inside=inlier[:,0]>0;n=int(inside.sum())
    if n<10:return None
    projected=cv2.perspectiveTransform(p[:,None,:],H)[:,0,:];error=np.linalg.norm(projected-q,axis=1)
    warped=cv2.warpPerspective(target,np.linalg.inv(H),(700,700));coverage=cv2.warpPerspective(np.ones((700,700),np.uint8),np.linalg.inv(H),(700,700),flags=cv2.INTER_NEAREST)>0;coverage&=mask>127
    photo_rmse=float(np.sqrt(np.mean((warped.astype(float)-source.astype(float))[coverage]**2)))
    return {'file':target_path.name,'matches':len(good),'inliers':n,'medianReprojectionPixels700':float(np.median(error[inside])),'coverage':float(coverage.mean()),'reprojectedGroundTruthRmse255':photo_rmse,'HsourceToNative700':H.tolist()}
with ThreadPoolExecutor(max_workers=4) as pool:rows=[r for r in pool.map(compare,sorted(RUN.glob('eval-gt-*.png'))) if r]
rows.sort(key=lambda r:(-r['inliers'],r['reprojectedGroundTruthRmse255']));rows=rows[:12]
out=HERE/f'native-match-pose-{a.pose}.json';out.write_text(json.dumps({'purpose':__doc__,'sourcePose':pose,'sourceFeatures':len(keys),'rankedOverlaps':rows},indent=2))
canvas=Image.new('RGB',(1200,6*430),'#192028');draw=ImageDraw.Draw(canvas)
for i,row in enumerate(rows[:6]):
    H=np.asarray(row['HsourceToNative700']);gt=cv2.imread(str(RUN/row['file']));pred=cv2.imread(str(RUN/row['file'].replace('eval-gt-','eval-render-')))
    for j,(label,image) in enumerate([('Source crop',source),('Native GT reprojected',cv2.warpPerspective(cv2.resize(gt,(700,700)),np.linalg.inv(H),(700,700))),('Native render reprojected',cv2.warpPerspective(cv2.resize(pred,(700,700)),np.linalg.inv(H),(700,700)))]):
        im=Image.fromarray(cv2.cvtColor(image,cv2.COLOR_BGR2RGB)).resize((400,400),Image.Resampling.LANCZOS);canvas.paste(im,(j*400,i*430+26));draw.text((j*400+5,i*430+5),f'{row["file"][8:13]}: {label} ({row["inliers"]} matches)',fill='white')
canvas.save(HERE/f'native-match-pose-{a.pose}.jpg',quality=95);print(json.dumps({'sourceFeatures':len(keys),'top':rows[:6]},indent=2))
