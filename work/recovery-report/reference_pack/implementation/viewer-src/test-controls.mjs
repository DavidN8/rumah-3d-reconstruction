import {chromium} from 'playwright';
import {writeFile} from 'node:fs/promises';
import {fileURLToPath,pathToFileURL} from 'node:url';
const root=new URL('../',import.meta.url),results=[];
const outputRoot=process.env.ROOM_TEST_OUTPUT_DIR?pathToFileURL(process.env.ROOM_TEST_OUTPUT_DIR.replace(/[\\/]?$/,'/')):new URL('analysis/',root);
const targetUrl=process.env.ROOM_REVIEW_URL||'http://127.0.0.1:53251/';
const standaloneUrl=process.env.ROOM_OFFLINE_PATH?pathToFileURL(process.env.ROOM_OFFLINE_PATH).href:new URL('review/iPhone-Full-Room-preview.html',root).href;
const browser=await chromium.launchPersistentContext(fileURLToPath(new URL('analysis/control-test-profile/',root)),{
  executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true,
  viewport:{width:1440,height:1000},deviceScaleFactor:1,
  args:['--enable-gpu','--use-angle=d3d11','--disable-background-timer-throttling','--disable-renderer-backgrounding']
});
const page=browser.pages()[0];const errors=[];page.on('pageerror',e=>errors.push(String(e)));
const state=()=>page.evaluate(()=>__room.state());
const delta=(a,b)=>b.position.map((x,i)=>x-a.position[i]);
const dot=(a,b)=>a.reduce((sum,x,i)=>sum+x*b[i],0);
const norm=a=>Math.hypot(...a);
function check(name,ok,evidence){results.push({name,pass:!!ok,evidence});if(!ok)console.log('FAIL',name,JSON.stringify(evidence));}
async function reset(){await page.click('#reset');await page.waitForTimeout(100);}
async function move(key,ms=220,shift=false){await reset();const a=await state();if(shift)await page.keyboard.down('Shift');await page.keyboard.down(key);await page.waitForTimeout(ms);await page.keyboard.up(key);if(shift)await page.keyboard.up('Shift');await page.waitForTimeout(350);const b=await state();return {a,b,d:delta(a,b)};}
try{
  await page.goto(targetUrl,{waitUntil:'load'});await page.waitForFunction(()=>window.__room?.ready,{timeout:60000});
  const renderer=await page.evaluate(()=>__room.rendererInfo());
  check('Hardware GPU',renderer.renderer.includes('RTX 5080'),renderer);
  for(const [key,axis,sign]of [['w','forward',1],['s','forward',-1],['a','right',-1],['d','right',1]]){
    const {a,b,d}=await move(key);const direction=dot(d,a[axis])*sign;
    check('WASD '+key,direction>.08&&Math.abs(d[1])<1e-8&&b.keys.length===0,{delta:d,directionalDistance:direction});
  }
  for(const [key,sign]of [['q',-1],['e',1],['Space',1],['c',-1]]){
    const {b,d}=await move(key);check('Vertical '+key,d[1]*sign>.08&&Math.hypot(d[0],d[2])<1e-8&&b.keys.length===0,{delta:d});
  }
  const normal=await move('w',300),fast=await move('w',300,true);const ratio=norm(fast.d)/norm(normal.d);
  check('Shift faster',ratio>2.2&&ratio<3.3,{ratio});
  for(const order of [['w','d'],['d','w']]){
    await reset();await page.keyboard.down('w');await page.keyboard.down('d');await page.waitForTimeout(100);await page.keyboard.up(order[0]);await page.waitForTimeout(80);await page.keyboard.up(order[1]);
    const released=await state();await page.waitForTimeout(600);const stopped=await state();await page.waitForTimeout(180);const later=await state();
    check('Overlap release '+order.join(' then '),released.keys.length===0&&norm(delta(stopped,later))<.0005,{keysBeforeCleanup:released.keys,driftAfterSettling:norm(delta(stopped,later))});
  }
  await reset();const box=await page.locator('#view').boundingBox();const x=box.x+box.width*.55,y=box.y+box.height*.5;
  const start=await state();await page.mouse.move(x,y);await page.mouse.down();await page.mouse.move(x+160,y,{steps:16});await page.mouse.up();const looked=await state();
  check('Mouse yaw right',dot(looked.forward,start.right)>.2&&Math.abs(looked.right[1])<1e-8&&norm(delta(start,looked))<1e-8,{before:start.forward,after:looked.forward,rightY:looked.right[1]});
  await page.mouse.move(x,y);await page.mouse.down();await page.mouse.move(x,y+120,{steps:12});await page.mouse.up();const tilted=await state();
  check('Mouse down, no roll',tilted.forward[1]<-.1&&Math.abs(tilted.right[1])<1e-8,{forward:tilted.forward,rightY:tilted.right[1]});
  await reset();const wa=await state();await page.mouse.move(x,y);await page.mouse.wheel(0,-120);await page.waitForTimeout(600);const wb=await state();
  check('Wheel forward',dot(delta(wa,wb),wa.forward)>.1&&Math.abs(wb.position[1]-wa.position[1])<1e-8,{delta:delta(wa,wb)});
  await reset();const ra=await state();await page.click('#rotate');const rb=await state();
  check('Rotate 90',Math.abs(dot(ra.forward,rb.forward))<1e-7&&norm(delta(ra,rb))<1e-8&&Math.abs(rb.right[1])<1e-8,{angleDot:dot(ra.forward,rb.forward)});
  await page.click('#orbit');const oa=await state();await page.mouse.move(x,y);await page.mouse.down();await page.mouse.move(x+150,y+90,{steps:16});await page.mouse.up();const ob=await state();
  check('Orbit keeps +Y upright',ob.mode==='orbit'&&Math.abs(ob.right[1])<1e-7&&norm(delta(oa,ob))>.1,{position:ob.position,rightY:ob.right[1]});
  await page.click('#top');const top=await state();check('Top view',top.mode==='orbit'&&top.forward[1]<-.999&&top.position[1]>2,{forward:top.forward,position:top.position});
  await page.keyboard.press('r');const home=await state();check('Keyboard reset',home.mode==='walk'&&norm(delta(ra,home))<1e-8&&Math.abs(home.forward[1])<1e-8,{position:home.position});
  for(let i=0;i<8;i++){
    await page.selectOption('#views',String(i));const s=await state();const c=await page.evaluate(i=>__room.data.presets[i],i);
    const distance=Math.hypot(...s.position.map((x,k)=>x-c.position[k]));const rotationDot=Math.abs(dot(s.quaternion,c.quaternion));
    check('Recorded preset '+i,distance<1e-8&&Math.abs(rotationDot-1)<1e-7,{name:c.name,distance,rotationDot});
  }
  await page.click('#compare');await page.waitForFunction(()=>document.getElementById('source-frame').complete&&document.getElementById('source-frame').naturalWidth>0);
  check('Source comparison',(await state()).comparison&&await page.locator('#source').isVisible(),{source:await page.locator('#source-frame').getAttribute('src')});
  await page.keyboard.press('w');await page.waitForTimeout(100);check('Preset supports immediate WASD',!(await state()).recorded&&!((await state()).comparison),await state());
  await reset();await page.evaluate(()=>__room.benchmark(true));await page.waitForTimeout(1200);await page.evaluate(()=>__room.benchmark(true));await page.waitForTimeout(4000);
  const times=await page.evaluate(()=>__room.timings());await page.evaluate(()=>__room.benchmark(false));
  const sorted=[...times].sort((a,b)=>a-b),mean=times.reduce((a,b)=>a+b,0)/times.length;
  const performance={frames:times.length,averageFps:1000/mean,medianMs:sorted[Math.floor(sorted.length*.5)],p95Ms:sorted[Math.floor(sorted.length*.95)],p99Ms:sorted[Math.floor(sorted.length*.99)],renderer};
  check('60 FPS target in this session',performance.averageFps>=58&&performance.p95Ms<20.5,performance);
  await page.click('#orbit');await page.evaluate(()=>__room.benchmark(true));await page.waitForTimeout(1000);await page.evaluate(()=>__room.benchmark(true));await page.waitForTimeout(2400);
  const orbitTimes=await page.evaluate(()=>__room.timings());await page.evaluate(()=>__room.benchmark(false));
  const orbitSorted=[...orbitTimes].sort((a,b)=>a-b),orbitMean=orbitTimes.reduce((a,b)=>a+b,0)/orbitTimes.length;
  const orbitPerformance={frames:orbitTimes.length,averageFps:1000/orbitMean,p95Ms:orbitSorted[Math.floor(orbitSorted.length*.95)],renderer:await page.evaluate(()=>__room.rendererInfo())};
  check('Full model orbit reaches 60 FPS',orbitPerformance.averageFps>=58&&orbitPerformance.p95Ms<20.5,orbitPerformance);
  // Load the actual standalone file with all network requests observed.
  const standalone=await browser.newPage();standalone.on('pageerror',e=>errors.push('standalone: '+String(e)));const network=[];standalone.on('request',r=>{if(/^https?:/.test(r.url()))network.push(r.url());});
  await standalone.goto(standaloneUrl,{waitUntil:'load'});
  await standalone.waitForFunction(()=>window.__room?.ready,null,{timeout:60000});
  await standalone.selectOption('#views','0');await standalone.click('#compare');
  await standalone.waitForFunction(()=>document.getElementById('source-frame').complete&&document.getElementById('source-frame').naturalWidth>0);
  check('Standalone works from file, fully offline',network.length===0&&await standalone.evaluate(()=>__room.ready),{networkRequests:network,sourceEmbedded:(await standalone.locator('#source-frame').getAttribute('src')).startsWith('data:')});
  await standalone.screenshot({path:fileURLToPath(new URL('fixed-standalone.png',outputRoot))});
  check('No browser errors',errors.length===0,errors);
}catch(error){
  check('Verification completed without exceptions',false,String(error));
  console.log('Verification exception',String(error));
}finally{
  await writeFile(new URL('fixed-controls-check.json',outputRoot),JSON.stringify({targetUrl,standaloneUrl,passed:results.every(r=>r.pass),checks:results,errors},null,2));
  console.log(JSON.stringify({passed:results.every(r=>r.pass),checks:results.length,failed:results.filter(r=>!r.pass),performance:results.find(r=>r.name.startsWith('60 FPS'))?.evidence},null,2));
  await browser.close();
  if(results.some(r=>!r.pass))process.exitCode=1;
}
