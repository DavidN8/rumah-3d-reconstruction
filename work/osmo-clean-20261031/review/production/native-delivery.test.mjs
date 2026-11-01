import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';
import {nativePolicy,nativeSparkFileType,validateModelHeader,waitForNativeDraw} from './native-delivery.js';
import {selectModel,readModel} from './loader-core.js';
const asset={representation:'gaussian',format:'spz',fileBytes:48_377_598,splats:2_997_515,cameraSet:'osmo'};
test('native display budget is separate from downloaded full scene',()=>{assert.equal(nativePolicy(asset,true).lodSplatCount,750000);assert.equal(nativePolicy(asset,false).lodSplatCount,2000000);assert.equal(nativePolicy(asset,true).baseSplats,2997515);assert.equal(nativePolicy(asset,true).nonLod,false);});
test('native selection uses its own cameras and rejects excessive source counts and bytes',()=>{const cameras={presets:[]};const manifest={models:{osmo:asset},cameraSets:{osmo:cameras}};assert.equal(selectModel(manifest,'osmo').cameraData,cameras);assert.throws(()=>nativePolicy({...asset,fileBytes:50000001}),/download budget/);assert.throws(()=>nativePolicy({...asset,splats:10000000}),/decoded splat budget/);});
test('format-aware download validation never treats HTML or arbitrary bytes as a valid native file',async()=>{const bytes=new Uint8Array(20);bytes[0]=31;bytes[1]=139;assert.equal(validateModelHeader(bytes,'spz'),true);assert.equal(validateModelHeader(bytes,'glb'),false);assert.equal((await readModel(new Response(bytes),20,{format:'spz'})).byteLength,20);await assert.rejects(readModel(new Response(new Uint8Array(20)),20,{format:'spz'}),/incomplete/);});
test('download formats map to the installed Spark SDK decoder names',async()=>{
 const require=createRequire(new URL('../../../mobile-20261029/package.json',import.meta.url));
 const definitions=await readFile(new URL('./types/defines.d.ts',pathToFileURL(require.resolve('@sparkjsdev/spark'))),'utf8');
 for(const [format,sdkName] of [['sog','PCSOGSZIP'],['spz','SPZ']]){
  const actual=definitions.match(new RegExp('\\b'+sdkName+' = "([^"]+)"'))?.[1];
  assert.ok(actual,'Installed SDK declares '+sdkName);assert.equal(nativeSparkFileType(format),actual);
 }
});

test('native ready waits for a sorted, nonempty draw instead of decoded data alone',async()=>{
 let updates=0,draws=0;
 const count=await waitForNativeDraw({update:async()=>{updates++;},draw:()=>{draws++;},activeSplats:()=>updates<3?0:1000,timeoutMs:1000});
 assert.equal(count,1000);assert.equal(draws,3);
});
test('a stuck first sort fails visibly and never draws after the deadline',async()=>{
 let finish,draws=0;
 const waiting=waitForNativeDraw({update:()=>new Promise(resolve=>{finish=resolve;}),draw:()=>draws++,activeSplats:()=>1000,timeoutMs:10});
 await assert.rejects(waiting,/could not draw/);finish();await new Promise(resolve=>setTimeout(resolve,20));assert.equal(draws,0);
});
test('an empty scene cannot report ready',async()=>{
 await assert.rejects(waitForNativeDraw({update:async()=>{},draw:()=>{},activeSplats:()=>0,timeoutMs:25}),/could not draw/);
});
test('cancelled native preparation cannot draw or report ready',async()=>{
 const controller=new AbortController();let finish,draws=0;
 const waiting=waitForNativeDraw({signal:controller.signal,update:()=>new Promise(resolve=>{finish=resolve;}),draw:()=>draws++,activeSplats:()=>1000,timeoutMs:1000});
 controller.abort();await assert.rejects(waiting,{name:'AbortError'});finish();await new Promise(resolve=>setTimeout(resolve,20));assert.equal(draws,0);
});
