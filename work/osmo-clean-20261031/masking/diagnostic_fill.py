from pathlib import Path
from PIL import Image
import cv2,numpy as np

HERE=Path(__file__).resolve().parent
DATA=Path('C:/Users/bombe/OneDrive/Documents/ChatGPT/Ruang Kamare/roomscan-reconstruction/data/20261031_OSMO360/clean-v3/dataset')
for cam,frame in [('cam0',1299),('cam1',1356),('cam1',1467),('cam1',1689)]:
    source=next((DATA/'images'/cam).glob(f'frame_{frame:06d}_*.jpg'))
    mask=np.asarray(Image.open(HERE/'operator-raw'/cam/source.with_suffix('.png').name))<128
    closed=cv2.morphologyEx(mask.astype(np.uint8),cv2.MORPH_CLOSE,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(65,65)))
    count,labels,stats,centers=cv2.connectedComponentsWithStats(1-closed,8)
    filled=closed.copy()
    holes=[]
    for i in range(1,count):
        x,y,w,h,area=stats[i]
        if x>0 and y>0 and x+w<3840 and y+h<3840 and area<800000:
            filled[labels==i]=1;holes.append(int(area))
    im=np.asarray(Image.open(source).convert('RGB').resize((900,900))).copy()
    original=cv2.resize(mask.astype(np.uint8),(900,900),interpolation=cv2.INTER_NEAREST)>0
    new=cv2.resize(filled,(900,900),interpolation=cv2.INTER_NEAREST)>0
    im[original]=(im[original]*.5+np.array([255,0,20])*.5).astype(np.uint8)
    added=new&~original
    im[added]=(im[added]*.4+np.array([0,255,255])*.6).astype(np.uint8)
    Image.fromarray(im).save(HERE/f'fill-{cam}-{frame}.jpg')
    print(cam,frame,'holes',sorted(holes,reverse=True)[:8])
