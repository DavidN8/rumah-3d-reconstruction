from pathlib import Path
import struct,json,math
here=Path(__file__).parent
def varint(d,p):
    v=0;s=0
    while True:
        b=d[p];p+=1;v|=(b&127)<<s
        if b<128:return v,p
        s+=7
        if s>70:raise ValueError('varint')
def fields(d):
    out={};p=0
    while p<len(d):
        key,p=varint(d,p);n=key>>3;w=key&7
        if w==0:v,p=varint(d,p)
        elif w==5:v=struct.unpack_from('<f',d,p)[0];p+=4
        elif w==1:v=struct.unpack_from('<d',d,p)[0];p+=8
        elif w==2:
            size,p=varint(d,p);v=d[p:p+size];p+=size
        else:raise ValueError((n,w,p))
        out.setdefault(n,[]).append((w,v))
    return out
def child(d,n):return fields(d[n][0][1])
d=fields((here/'djmd-first.bin').read_bytes())
print('Root',[(n,[(w,len(v) if isinstance(v,bytes) else v) for w,v in vv]) for n,vv in d.items()])
stream=child(d,2)
print('Stream',[(n,[(w,len(v) if isinstance(v,bytes) else v) for w,v in vv]) for n,vv in stream.items()])
pano_field=5 if len(stream[5][0][1])>100 else 6
pano=child(stream,pano_field)
out={}
names={1:'fx',2:'fy',3:'cx',4:'cy',5:'k1',6:'k2',7:'k3',8:'k4',9:'xi',10:'width',11:'height',12:'yaw',13:'pitch',14:'roll',15:'k5',16:'k6',17:'k7',18:'k8',19:'k9',20:'p',21:'q',22:'occlusion_x',23:'occlusion_y',24:'lens_model',25:'temperature',26:'cam_imu_extri_q',27:'tangent_coeff',28:'cam_extri_q'}
for num in pano:
    slot=child(pano,num);result={}
    for n,values in slot.items():
        w,v=values[0]
        if w==5 or w==0:result[names.get(n,str(n))]=v
        elif n in (20,21,22,23,27) and w==2:
            result[names[n]]=list(struct.unpack('<'+'f'*(len(v)//4),v))
        elif n in (26,28):result[names[n]]={str(k):vv[0][1] for k,vv in fields(v).items()}
    if result.get('fx',0):out[str(num)]=result
result={'source':f'Original OSV first djmd sample, StreamMeta field{pano_field} PanoDewarpParams; OpenOSV DewarpParams schema interpretation. OQ102 uses Avata-style StreamMeta layout.', 'schema':'dvtm_OQ102.proto','calibration_model':'Kannala-Brandt five radial terms','slots':out}
(here/'calibration.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))
