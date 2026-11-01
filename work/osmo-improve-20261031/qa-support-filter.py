"""Conservative spatial-evidence face filter; raw GLB attribute/image preservation.

Support = near the retained baseline surface vertices OR near good main-SfM
points. A face survives when at least two of its original vertices are supported.
This does not move vertices, fill caps, change heights or repair camera poses.
"""
import os
os.environ['OMP_NUM_THREADS']='2'
os.environ['OPENBLAS_NUM_THREADS']='2'
from pathlib import Path
import argparse
import copy
import hashlib
import json
import struct
import sys
import time
import cv2
import numpy as np
from scipy.spatial import cKDTree
from scipy.spatial.transform import Rotation

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/'qa-deps'))
sys.path.insert(0,str(HERE.parent/'osmo-reconstruct-20261031'))
import trimesh
from seed_fisheye import read_model,qvec_to_rotmat,Fisheye
CAPTURE=Path(r'C:\Users\bombe\OneDrive\Documents\ChatGPT\Ruang Kamare\roomscan-reconstruction\data\20261031_OSMO360')
DTYPES={5120:np.dtype('i1'),5121:np.dtype('u1'),5122:np.dtype('<i2'),5123:np.dtype('<u2'),5125:np.dtype('<u4'),5126:np.dtype('<f4')}
COMPONENTS={'SCALAR':1,'VEC2':2,'VEC3':3,'VEC4':4,'MAT2':4,'MAT3':9,'MAT4':16}
sha=lambda data:hashlib.sha256(data).hexdigest()

def load_glb(path):
    data=Path(path).read_bytes()
    magic,version,size=struct.unpack_from('<III',data)
    if magic!=0x46546c67 or version!=2 or size!=len(data):raise ValueError('Not a complete GLB2')
    doc=None;binary=None;offset=12
    while offset<len(data):
        length,kind=struct.unpack_from('<II',data,offset);offset+=8;chunk=data[offset:offset+length];offset+=length
        if kind==0x4E4F534A:doc=json.loads(chunk)
        elif kind==0x004E4942:binary=chunk
    if doc is None or binary is None:raise ValueError('Embedded GLB JSON/BIN required')
    if len(doc.get('buffers',[]))!=1 or doc['buffers'][0].get('uri'):raise ValueError('Only one embedded buffer supported')
    if doc.get('animations') or doc.get('skins'):raise ValueError('Refusing animation/skin accessor rewrites')
    if any(x in doc.get('extensionsUsed',[]) for x in ['EXT_meshopt_compression','KHR_draco_mesh_compression']):raise ValueError('Use the uncompressed source GLB')
    return doc,binary

def accessor(doc,binary,index):
    item=doc['accessors'][index]
    if item.get('sparse'):raise ValueError('Sparse accessor not supported')
    view=doc['bufferViews'][item['bufferView']];dtype=DTYPES[item['componentType']];width=COMPONENTS[item['type']]
    stride=view.get('byteStride',dtype.itemsize*width)
    return np.ndarray((item['count'],width),dtype=dtype,buffer=binary,offset=view.get('byteOffset',0)+item.get('byteOffset',0),strides=(stride,dtype.itemsize))

def node_matrices(doc):
    matrices={};scene=doc['scenes'][doc.get('scene',0)]
    def visit(index,parent):
        node=doc['nodes'][index]
        if 'matrix' in node:local=np.array(node['matrix']).reshape(4,4).T
        else:
            local=np.eye(4);local[:3,:3]=Rotation.from_quat(node.get('rotation',[0,0,0,1])).as_matrix()@np.diag(node.get('scale',[1,1,1]));local[:3,3]=node.get('translation',[0,0,0])
        world=parent@local
        if 'mesh' in node:matrices.setdefault(node['mesh'],[]).append(world)
        for child in node.get('children',[]):visit(child,world)
    for index in scene['nodes']:visit(index,np.eye(4))
    if any(len(v)!=1 for v in matrices.values()):raise ValueError('Shared mesh instances need per-instance support; refusing a guessed union')
    return {k:v[0] for k,v in matrices.items()}

def good_sparse():
    path=HERE/'qa-good-sfm.npz';report=HERE/'qa-good-sfm.json'
    if path.exists():return np.load(path)['points'],json.loads(report.read_text())
    cameras,images,points=read_model(CAPTURE/'lite-v1/dataset/sparse/0')
    ids=[pid for pid,p in points.items() if p['track_len']>=4];lookup={pid:j for j,pid in enumerate(ids)}
    support=np.zeros(len(ids),np.int32);tested=np.zeros(len(ids),np.int32);sum_error=np.zeros(len(ids))
    for im in images.values():
        obs=[(i,lookup[int(pid)],int(pid)) for i,pid in enumerate(im['point3D_ids']) if int(pid) in lookup]
        if not obs:continue
        ix=np.array([x[0] for x in obs]);pi=np.array([x[1] for x in obs]);xyz=np.array([points[x[2]]['xyz'] for x in obs]);xy=im['points2D_xy'][ix]
        projected,valid=Fisheye(cameras[im['camera_id']]).project(xyz@qvec_to_rotmat(im['qvec']).T+im['tvec'])
        error=np.linalg.norm(projected-xy,axis=1);pixel=np.rint(xy).astype(int)
        mask=cv2.imread(str(CAPTURE/'lite-v1/dataset/masks'/Path(im['name']).with_suffix('.png')),0)
        inside=(pixel[:,0]>=0)&(pixel[:,0]<mask.shape[1])&(pixel[:,1]>=0)&(pixel[:,1]<mask.shape[0])
        good=valid&inside&(error<=2)
        rows=np.flatnonzero(good);rows=rows[mask[pixel[rows,1],pixel[rows,0]]>127]
        np.add.at(support,pi[rows],1);np.add.at(tested,pi[valid],1);np.add.at(sum_error,pi[valid],error[valid])
    keep=(support>=3)&(sum_error/np.maximum(tested,1)<=1.5)
    xyz=np.array([points[pid]['xyz'] for pid in ids])[keep]
    np.savez_compressed(path,points=xyz,point_ids=np.array(ids)[keep])
    data={'total_main_points':len(points),'track4_candidates':len(ids),'good_points':len(xyz),'minimum_track_length':4,'minimum_masked_observations_at_actual_reprojection_le2':3,'maximum_mean_actual_reprojection_px':1.5,'writer_point_error_field_used':False,'source':'accepted normalized main SfM component','cache_sha256':sha(path.read_bytes())}
    report.write_text(json.dumps(data,indent=2));return xyz,data

def write_variant(doc,binary,prepared,threshold,min_supported,destination):
    output=copy.deepcopy(doc);output['bufferViews']=[];output['accessors']=[];newbin=bytearray();checks=[]
    def view(content,target=None):
        while len(newbin)%4:newbin.append(0)
        item={'buffer':0,'byteOffset':len(newbin),'byteLength':len(content)}
        if target:item['target']=target
        index=len(output['bufferViews']);output['bufferViews'].append(item);newbin.extend(content);return index
    image_checks=[]
    for image_index,image in enumerate(output.get('images',[])):
        if 'bufferView' not in image:continue
        old=doc['bufferViews'][image['bufferView']];payload=binary[old.get('byteOffset',0):old.get('byteOffset',0)+old['byteLength']]
        image['bufferView']=view(payload);image_checks.append({'image':image_index,'bytes':len(payload),'sha256':sha(payload)})
    total=0;kept=0;support_counts=[]
    for mesh_index,mesh in enumerate(output['meshes']):
        new_primitives=[]
        for primitive_index,primitive in enumerate(mesh['primitives']):
            source=doc['meshes'][mesh_index]['primitives'][primitive_index];info=prepared[(mesh_index,primitive_index)]
            supported=(info['baseline_distance']<=threshold)|(info['sfm_distance']<=.04)
            face_keep=supported[info['faces']].sum(axis=1)>=min_supported
            faces=info['faces'][face_keep];total+=len(info['faces']);kept+=len(faces)
            support_counts.append({'mesh':mesh_index,'primitive':primitive_index,'source_faces':len(info['faces']),'retained_faces':len(faces),'supported_vertices':int(supported.sum()),'vertices_total':len(supported)})
            if not len(faces):continue
            used,remapped=np.unique(faces.ravel(),return_inverse=True)
            new_attributes={}
            for semantic,index in source['attributes'].items():
                raw=accessor(doc,binary,index);selected=np.ascontiguousarray(raw[used]);meta=copy.deepcopy(doc['accessors'][index])
                meta.update(bufferView=view(selected.tobytes(),34962),byteOffset=0,count=len(used))
                if 'min' in meta or semantic=='POSITION':meta['min']=selected.min(axis=0).tolist()
                if 'max' in meta or semantic=='POSITION':meta['max']=selected.max(axis=0).tolist()
                new_attributes[semantic]=len(output['accessors']);output['accessors'].append(meta)
                checks.append({'mesh':mesh_index,'primitive':primitive_index,'semantic':semantic,'retained_attribute_bytes_sha256':sha(selected.tobytes()),'original_selected_attribute_bytes_identical':True})
            index_meta=copy.deepcopy(doc['accessors'][source['indices']]);index_dtype=DTYPES[index_meta['componentType']]
            packed_indices=np.ascontiguousarray(remapped.astype(index_dtype).reshape(-1,1))
            index_meta.update(bufferView=view(packed_indices.tobytes(),34963),byteOffset=0,count=len(remapped),min=[0],max=[int(remapped.max())])
            primitive['attributes']=new_attributes;primitive['indices']=len(output['accessors']);output['accessors'].append(index_meta)
            new_primitives.append(primitive)
        if not new_primitives:raise ValueError('A whole mesh would be empty; inspect support/frame assumptions')
        mesh['primitives']=new_primitives
    output['buffers']=[{'byteLength':len(newbin)}]
    encoded=json.dumps(output,separators=(',',':')).encode();encoded+=b' '*((-len(encoded))%4);newbin+=b'\0'*((-len(newbin))%4)
    result=struct.pack('<III',0x46546c67,2,12+8+len(encoded)+8+len(newbin))+struct.pack('<II',len(encoded),0x4E4F534A)+encoded+struct.pack('<II',len(newbin),0x004E4942)+newbin
    destination.write_bytes(result)
    verified,verifybin=load_glb(destination)
    for field in ('nodes','materials','textures','samplers','scenes','scene'):
        if verified.get(field)!=doc.get(field):raise AssertionError('Preserved scene/material field changed: '+field)
    for item in image_checks:
        image=verified['images'][item['image']];bv=verified['bufferViews'][image['bufferView']];payload=verifybin[bv.get('byteOffset',0):bv.get('byteOffset',0)+bv['byteLength']]
        if sha(payload)!=item['sha256']:raise AssertionError('Embedded source image changed')
    # Accessor-byte hashes attest that compaction did not move/recompute vertex data.
    for item in checks:
        primitive=verified['meshes'][item['mesh']]['primitives'][item['primitive']]
        actual=accessor(verified,verifybin,primitive['attributes'][item['semantic']]).tobytes()
        if sha(actual)!=item['retained_attribute_bytes_sha256']:raise AssertionError('Retained attribute bytes changed')
    return {'file':str(destination),'bytes':len(result),'sha256':sha(result),'baseline_support_distance':threshold,'sfm_support_distance':.04,'minimum_supported_vertices_per_face':min_supported,'source_faces':total,'retained_faces':kept,'removed_faces':total-kept,'primitives':support_counts,'attribute_checks':checks,'embedded_image_checks':image_checks,'nodes_materials_textures_samplers_unchanged':True,'height_crop':False,'vertex_position_changes':False,'normal_changes':False,'uv_changes':False,'invented_caps':False}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--input',required=True);parser.add_argument('--baseline',required=True);parser.add_argument('--prefix',required=True);parser.add_argument('--thresholds',default='.05,.08,.12');parser.add_argument('--min-supported',type=int,default=2);args=parser.parse_args()
    source=Path(args.input).resolve();baseline=Path(args.baseline).resolve();prefix=Path(args.prefix).resolve();allowed=CAPTURE/'recovery-v2/exports'
    if not prefix.is_relative_to(allowed.resolve()):raise ValueError('Filtered outputs must stay under recovery-v2/exports')
    if args.min_supported not in (1,2,3):raise ValueError('Face support count must be1,2or3')
    thresholds=[float(value) for value in args.thresholds.split(',')];destinations=[prefix.with_name(prefix.name+f'-{round(t*100):02d}cm.glb') for t in thresholds]
    if any(path.exists() for path in destinations):raise ValueError('Filtered variant already exists; do not overwrite')
    start=time.monotonic();doc,binary=load_glb(source);matrices=node_matrices(doc)
    print('Loading baseline spatial support',flush=True);baseline_mesh=trimesh.load_scene(baseline,process=False).to_geometry();basepoints=np.unique(np.asarray(baseline_mesh.vertices),axis=0);baseline_tree=cKDTree(basepoints)
    sfmpoints,sfm_report=good_sparse();sfm_tree=cKDTree(sfmpoints)
    prepared={}
    for mesh_index,mesh in enumerate(doc['meshes']):
        if mesh_index not in matrices:raise ValueError('Unused mesh lacks a world transform')
        matrix=matrices[mesh_index]
        for primitive_index,primitive in enumerate(mesh['primitives']):
            if primitive.get('mode',4)!=4 or primitive.get('targets') or 'indices' not in primitive:raise ValueError('Only indexed static triangle primitives supported')
            position_meta=doc['accessors'][primitive['attributes']['POSITION']]
            if position_meta.get('normalized'):raise ValueError('Use the float source GLB')
            points=accessor(doc,binary,primitive['attributes']['POSITION']).astype(np.float64);world=points@matrix[:3,:3].T+matrix[:3,3]
            faces=accessor(doc,binary,primitive['indices']).reshape(-1,3).astype(np.int64)
            print('Querying support for',len(points),'vertices',flush=True)
            dist=baseline_tree.query(world,workers=2)[0];sdist=sfm_tree.query(world,workers=2)[0]
            prepared[(mesh_index,primitive_index)]={'faces':faces,'baseline_distance':dist,'sfm_distance':sdist}
    reports=[]
    for threshold,destination in zip(thresholds,destinations):
        report=write_variant(doc,binary,prepared,threshold,args.min_supported,destination);reports.append(report);print('Filtered',destination.name,report['retained_faces'],'faces',flush=True)
    result={'input':str(source),'input_sha256':sha(source.read_bytes()),'baseline':str(baseline),'baseline_support_vertices':len(basepoints),'sfm_support':sfm_report,'method':'At least2 face vertices close to baseline vertices or good main-SfM points; no per-vertex unseen self-occlusion cull, no height crop or caps. Retained position/normal/UV/color bytes and embedded source images preserved.','variants':reports,'elapsed_seconds':time.monotonic()-start}
    output=HERE/('qa-'+prefix.name+'-support.json');output.write_text(json.dumps(result,indent=2));print(json.dumps({'report':str(output),'elapsed_seconds':result['elapsed_seconds']},indent=2),flush=True)
if __name__=='__main__':main()
