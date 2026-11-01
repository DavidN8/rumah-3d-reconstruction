import {build} from 'esbuild';
import {chromium} from 'playwright';
import {mkdir,readFile,writeFile} from 'node:fs/promises';
import {spawn} from 'node:child_process';
import {fileURLToPath} from 'node:url';
const root=new URL('../',import.meta.url),base=fileURLToPath(root),stage=process.argv[2]||'pilot',out=new URL(`recovery-v2/analysis/verification-${stage}/`,root),port=53253;
await mkdir(out,{recursive:true});
const server=spawn('C:/Python314/python.exe',['-m','http.server',String(port),'--bind','127.0.0.1','--directory',base],{windowsHide:true,stdio:'ignore'});
let browser;
try{
 for(let i=0;i<30;i++){try{const r=await fetch(`http://127.0.0.1:${port}/recovery-v2/analysis/original-components.json`);if(r.ok)break;}catch{}await new Promise(r=>setTimeout(r,200));}
 browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true,args:['--enable-gpu','--use-angle=d3d11','--js-flags=--expose-gc']});
 const page=await browser.newPage({viewport:{width:1440,height:1000},deviceScaleFactor:1}),errors=[];page.on('pageerror',e=>{errors.push(String(e));console.log('PAGE ERROR',String(e));});
 const count=stage==='pilot'?2:8;
 for(const [label,path]of (process.env.ROOM_DEPTH_ONLY==='1'?[]:[['before',process.env.ROOM_BEFORE_DIR||'review/'],['after',process.env.ROOM_AFTER_DIR||`recovery-v2/review/${stage}/`]])){
  await page.goto(`http://127.0.0.1:${port}/${path}`,{waitUntil:'load'});await page.waitForFunction(()=>window.__room?.ready,null,{timeout:120000});
  for(let i=0;i<count;i++){await page.selectOption('#views',String(i));if(i===0)await page.click('#compare');await page.waitForFunction(()=>document.getElementById('source-frame').complete&&document.getElementById('source-frame').naturalWidth>0);await page.waitForTimeout(200);await page.screenshot({path:fileURLToPath(new URL(`${label}-${String(i+1).padStart(2,'0')}.png`,out))});}
  await page.click('#reset');await page.click('#orbit');await page.waitForTimeout(200);await page.screenshot({path:fileURLToPath(new URL(`${label}-overview.png`,out))});
 }
 await build({entryPoints:[fileURLToPath(new URL('recovery-depth-client.js',import.meta.url))],outfile:fileURLToPath(new URL('depth.bundle.js',out)),bundle:true,format:'iife',minify:true,logLevel:'silent'});
 await writeFile(new URL('depth.html',out),'<!doctype html><meta charset="utf-8"><body><script src="depth.bundle.js"></script></body>');
 await page.goto(`http://127.0.0.1:${port}/recovery-v2/analysis/verification-${stage}/depth.html`);await page.waitForFunction(()=>window.depthReady,null,{timeout:30000});
 const metadata=JSON.parse(await readFile(new URL(process.env.ROOM_METADATA_FILE||`recovery-v2/review/${stage}/cameras.json`,root),'utf8')),results=[];
 const targetModel=process.env.ROOM_TARGET_MODEL_PATH||`/recovery-v2/review/${stage}/models/iphone-full-room.glb`;
 const models=(process.env.ROOM_COMPARE_BASELINE==='1'||/(compact|fast)(-packed)?$/.test(stage))?[['raw',process.env.ROOM_RAW_BASELINE_PATH||'/recovery-v2/exports/apartment-raw.glb'],['compact',targetModel]]:[['raw',targetModel]];
 for(const [kind,path]of models){await page.evaluate(async path=>depthAudit.load(path),path);const rows=[];
  for(let i=0;i<count;i++){const r=await page.evaluate(({c,key,kind})=>depthAudit.measure(c,key,kind),{c:metadata.presets[i],key:metadata.presets[i].name,kind});await writeFile(new URL(`${kind}-depth-${i+1}.png`,out),Buffer.from(r.png.split(',')[1],'base64'));delete r.png;rows.push(r);}
  const r=await page.evaluate(kind=>depthAudit.measure(null,'dollhouse',kind,true),kind);await writeFile(new URL(`${kind}-depth-overview.png`,out),Buffer.from(r.png.split(',')[1],'base64'));delete r.png;rows.push(r);results.push({kind,views:rows});
 }
 await writeFile(new URL('depth-and-hole-checks.json',out),JSON.stringify({results,errors,interpretation:'Flags require visual review. Compaction comparisons use identical cameras and a fixed mask. No claim that a zero-background ray proves a missing measured wall.'},null,2));
 console.log(JSON.stringify({stage,errors,depth:results.map(r=>({kind:r.kind,views:r.views.map(v=>({name:v.name,holes:v.hole_pixel_fraction,doubleLayers:v.double_front_layer_fraction,newHoles:v.new_hole_pixel_fraction,compactionGate:v.compaction_hole_gate}))}))},null,2));
}finally{if(browser)await browser.close();server.kill();}
