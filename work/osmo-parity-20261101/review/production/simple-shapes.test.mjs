import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';
import {validateShapes,shapeVisible,buildShapes} from './simple-shapes.js';
const read=async name=>JSON.parse(await readFile(new URL(name,import.meta.url),'utf8'));
const box={kind:'object',type:'box',center:[0,.5,0],size:[1,1,1],yaw:0,color:'#aabbcc'};
test('shape files are validated before anything is drawn',()=>{
 assert.equal(validateShapes({version:1,shapes:[box]}).shapes.length,1);
 for(const bad of [{...box,type:'cone'},{...box,size:[1,0,1]},{...box,color:'red'},{...box,center:[0,NaN,0]},{...box,outward:[1]}])
  assert.throws(()=>validateShapes({version:1,shapes:[bad]}),/malformed/);
 assert.throws(()=>validateShapes({version:2,shapes:[box]}),/malformed/);
});
test('the overview hides ceilings and only the exterior walls that face the camera',()=>{
 const wall={...box,kind:'wall',center:[2,1,0],outward:[1,0]},camera={x:10,z:0};
 assert.equal(shapeVisible(wall,true,camera),false);assert.equal(shapeVisible(wall,true,{x:-10,z:0}),true);
 assert.equal(shapeVisible({...box,kind:'ceiling'},true,camera),false);assert.equal(shapeVisible({...box,kind:'wall'},true,camera),true);
 assert.equal(shapeVisible(wall,false,camera),true);
});
test('the shipped shape file matches the packed model and builds into three.js meshes',async()=>{
 const candidate=await read('./candidate.json'),shapes=await read(candidate.simpleShapes),packing=await read(candidate.packingReport);
 assert.equal(shapes.source.sha256,packing.sourceSha256);validateShapes(shapes);
 const require=createRequire(new URL('../../../mobile-20261029/package.json',import.meta.url));
 const THREE=await import(pathToFileURL(require.resolve('three')).href);
 const group=buildShapes(THREE,shapes);assert.equal(group.children.length,shapes.shapes.length);
 const mesh=group.children.find(m=>m.userData.shape.type==='box');assert.deepEqual(mesh.scale.toArray(),mesh.userData.shape.size);
 group.userData.dispose();
});
