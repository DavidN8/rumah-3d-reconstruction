import fs from 'node:fs/promises';import {createRequire} from 'node:module';import path from 'node:path';import {fileURLToPath} from 'node:url';
const here=path.dirname(fileURLToPath(import.meta.url)),W=process.argv[2]==='poisson'?path.resolve(here,'../poisson-pilot'):here,require=createRequire(path.resolve(W,'../../../mobile-20261029/package.json'));
const {NodeIO,Document}=require('@gltf-transform/core'),{KHRMaterialsUnlit,ALL_EXTENSIONS}=require('@gltf-transform/extensions'),{meshopt}=require('@gltf-transform/functions'),{MeshoptSimplifier:S,MeshoptEncoder:E,MeshoptDecoder:D}=require('meshoptimizer');
await Promise.all([S.ready,E.ready,D.ready]);
const array=async(name,Type)=>{const b=await fs.readFile(path.join(W,name+'.bin'));return new Type(b.buffer,b.byteOffset,b.byteLength/Type.BYTES_PER_ELEMENT);};
const [position,normal,color,indices]=await Promise.all([array('position',Float32Array),array('normal',Float32Array),array('color',Uint8Array),array('indices',Uint32Array)]);
const [simple,error]=S.simplify(indices,position,3,3_600_000,.002,[]);console.log('Simplified',simple.length/3,'relative error',error);
const [remap,count]=S.compactMesh(simple);
function compact(src,Type){const out=new Type(count*3);for(let old=0;old<remap.length;old++){const next=remap[old];if(next!==0xffffffff)out.set(src.subarray(old*3,old*3+3),next*3);}return out;}
const doc=new Document(),buffer=doc.createBuffer(),unlit=doc.createExtension(KHRMaterialsUnlit),mat=doc.createMaterial('Captured room').setExtension('KHR_materials_unlit',unlit.createUnlit()).setDoubleSided(true);
const p=doc.createPrimitive().setMaterial(mat).setIndices(doc.createAccessor().setType('SCALAR').setArray(simple).setBuffer(buffer));
for(const [name,src,Type,normalized] of [['POSITION',position,Float32Array,false],['NORMAL',normal,Float32Array,false],['COLOR_0',color,Uint8Array,true]])p.setAttribute(name,doc.createAccessor(name).setType('VEC3').setArray(compact(src,Type)).setNormalized(normalized).setBuffer(buffer));
doc.createScene().addChild(doc.createNode().setMesh(doc.createMesh().addPrimitive(p)));
await doc.transform(meshopt({encoder:E,level:'high',quantizePosition:16,quantizeNormal:8,quantizeColor:8}));
const io=new NodeIO().registerExtensions(ALL_EXTENSIONS).registerDependencies({'meshopt.encoder':E,'meshopt.decoder':D});await io.write(path.join(W,'vertex-preview.glb'),doc);
console.log(JSON.stringify({triangles:simple.length/3,vertices:count,error,bytes:(await fs.stat(path.join(W,'vertex-preview.glb'))).size}));
