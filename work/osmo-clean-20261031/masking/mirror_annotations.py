"""Explicit per-selected-frame mirror glass contours, manually traced at 640 px.

This is not interpolation and not a semantic 'person' reflection mask. Every
listed contour encloses the full visible bathroom mirror, including virtual
walls and reflected doors. Finalization adds a 16-native-pixel safety margin.
Source images and operator masks remain unchanged.
"""
from pathlib import Path
import json
from PIL import Image,ImageDraw

HERE=Path(__file__).resolve().parent
# Contours are in the 640x640 native-aspect preview coordinate system.
POLYGONS={
 'cam0':{
  564:[[366,282],[488,318],[428,503],[305,480]],
  573:[[304,263],[444,302],[390,488],[250,460]],
  585:[[261,248],[407,291],[348,473],[216,446]],
  591:[[247,245],[396,286],[335,472],[209,442]],
  600:[[228,242],[377,278],[309,474],[169,445]],
  609:[[220,246],[357,279],[298,470],[184,442]],
  615:[[232,259],[357,279],[299,472],[204,439]],
  621:[[267,275],[382,286],[329,483],[241,441]],
  627:[[312,291],[429,302],[420,366],[393,432],[360,496],[279,455]],
  636:[[416,316],[552,316],[546,385],[523,451],[486,513],[391,488]],
  642:[[489,333],[640,313],[640,482],[558,525],[433,489]],
  645:[[537,337],[640,318],[640,459],[566,522],[486,503]],
  651:[[599,348],[640,336],[640,438],[586,521],[550,504]],
  1482:[[48,310],[88,321],[89,401],[105,439],[65,423],[47,374]],
  1485:[[65,321],[126,340],[120,444],[79,423],[66,376]],
  1491:[[94,338],[194,363],[178,470],[102,437]],
  1497:[[124,352],[246,388],[204,488],[120,445]],
  1506:[[169,375],[299,427],[247,514],[153,466]],
  1515:[[222,403],[342,459],[282,536],[183,485]],
  1524:[[265,419],[384,473],[317,544],[211,490]],
  1530:[[280,430],[389,478],[327,545],[226,504]],
  1539:[[311,450],[401,497],[346,555],[242,512]],
  1551:[[320,470],[405,514],[345,574],[240,534]],
  1557:[[302,471],[390,507],[350,576],[228,528]],
  1563:[[283,452],[370,486],[330,553],[209,510]],
  1572:[[207,391],[289,411],[289,485],[160,478]],
  1575:[[177,376],[259,391],[254,472],[140,472]],
  1584:[[58,330],[143,345],[199,428],[75,461],[58,396]],
  1590:[[12,323],[103,332],[160,415],[48,465],[20,417],[12,371]],
  1593:[[0,320],[77,327],[137,411],[36,472],[8,423],[0,373]],
  1599:[[0,337],[26,330],[103,425],[48,479],[13,418]],
  1608:[[0,355],[20,389],[43,439],[63,470],[47,490],[18,452],[0,412]],
 },
 'cam1':{
  642:[[0,321],[31,315],[51,436],[123,538],[83,537],[0,425]],
  645:[[0,326],[66,311],[88,436],[181,534],[112,545],[0,447]],
  651:[[0,348],[132,308],[156,419],[224,501],[146,544],[49,487]],
  660:[[92,315],[225,286],[281,458],[172,497]],
  666:[[145,306],[267,275],[311,437],[208,471]],
  678:[[219,284],[341,258],[382,414],[282,453]],
  687:[[260,273],[369,251],[405,398],[315,435]],
  696:[[300,251],[380,239],[411,378],[341,400]],
  708:[[369,247],[403,244],[425,367],[395,381]],
  714:[[404,246],[418,244],[436,360],[425,368]],
 }
}

def main():
    for camera, relative in [('cam1','geometry/second-mirror-cam1.json'),
                             ('cam0','review/second-mirror-cam0-approach.json')]:
        source=HERE.parent/relative
        if source.exists():
            other=json.loads(source.read_text())
            if 'polygons' in other:other=other['polygons']
            if 'frames' in other:other=other['frames']
            POLYGONS[camera].update({int(k):v for k,v in other.items() if str(k).isdigit()})
    manifest=json.loads((HERE.parent/'frame-selection.json').read_text())
    output=HERE/'review-annotations.json'
    data=json.loads(output.read_text()) if output.exists() else {'frames':{}}
    data.update({'coordinate_system':'normalized XY on native source image, not panorama',
                 'optical_circle':{'cam0':[.5,.5,.48],'cam1':[.5,.5,.48]},
                 'mirror_note':'Full visible glass, manually traced independently per selected frame at640; native margin16px; no person-only or SAM semantic holes.'})
    for cam in ['cam0','cam1']:
        entries=[]
        for r in manifest['selected']:
            key=f"{cam}/{r['filename']}"
            entry=data['frames'].setdefault(key,{'reviewed':False})
            entry['source_frame']=r['source_frame']
            entry['time_seconds']=r['time_seconds']
            entry['mirror_polygons']=[[[x/640,y/640] for x,y in POLYGONS[cam][r['source_frame']]]] if r['source_frame'] in POLYGONS[cam] else []
            if entry['mirror_polygons']:
                entries.append(r)
        tile=400
        canvas=Image.new('RGB',(4*tile,((len(entries)+3)//4)*(tile+30)),'#24282e')
        draw=ImageDraw.Draw(canvas)
        for j,r in enumerate(entries):
            im=Image.open(HERE.parent/'thumbnails'/cam/f"sample_{r['source_frame']//3+1:06d}.jpg").convert('RGBA')
            overlay=Image.new('RGBA',im.size)
            d=ImageDraw.Draw(overlay)
            d.polygon(POLYGONS[cam][r['source_frame']],fill=(255,0,100,100),outline=(255,0,50,255),width=3)
            im=Image.alpha_composite(im,overlay).convert('RGB').resize((tile,tile))
            x,y=j%4*tile,j//4*(tile+30)
            canvas.paste(im,(x,y+30));draw.text((x+5,y+5),f"{cam} n={r['source_frame']}",fill='white')
        (HERE/'review').mkdir(exist_ok=True)
        canvas.save(HERE/'review'/f'mirror-polygons-{cam}.jpg',quality=93)
    output.write_text(json.dumps(data,indent=2))
    print('Wrote explicit mirror contours; visual operator review remains required.')

if __name__=='__main__':main()
