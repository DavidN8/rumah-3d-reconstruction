import {chromium} from 'playwright';
import {mkdir,writeFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
const prefix=process.env.ROOM_VERIFY_PREFIX||'fixed';
const root=new URL('../',import.meta.url),out=new URL(`analysis/${prefix}-renders/`,root);
await mkdir(out,{recursive:true});
const browser=await chromium.launchPersistentContext(fileURLToPath(new URL('analysis/browser-profile/',root)),{
  executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true,
  viewport:{width:1440,height:1000},deviceScaleFactor:1,
  args:['--enable-gpu','--use-angle=d3d11','--disable-background-timer-throttling','--disable-renderer-backgrounding']
});
const page=browser.pages()[0];const errors=[];page.on('pageerror',e=>errors.push(String(e)));
await page.goto(process.env.ROOM_TEST_URL||'http://127.0.0.1:53251/',{waitUntil:'load'});
await page.waitForFunction(()=>window.__room?.ready,{timeout:60000});
await page.screenshot({path:fileURLToPath(new URL(`analysis/${prefix}-start.png`,root))});
console.log(JSON.stringify(await page.evaluate(()=>({state:__room.state(),renderer:__room.rendererInfo()})),null,2));
for(let i=0;i<8;i++){
  await page.selectOption('#views',String(i));
  if(i===0)await page.click('#compare');
  await page.waitForFunction(()=>document.getElementById('source-frame').complete&&document.getElementById('source-frame').naturalWidth>0);
  await page.waitForTimeout(200);
  await page.screenshot({path:fileURLToPath(new URL(`${String(i+1).padStart(2,'0')}-compare.png`,out))});
}
await page.click('#reset');await page.click('#orbit');await page.waitForTimeout(200);
await page.screenshot({path:fileURLToPath(new URL(`analysis/${prefix}-isometric.png`,root))});
await page.click('#top');await page.waitForTimeout(200);
await page.screenshot({path:fileURLToPath(new URL(`analysis/${prefix}-top.png`,root))});
await writeFile(new URL(`analysis/${prefix}-viewer-initial-check.json`,root),JSON.stringify({errors,renderer:await page.evaluate(()=>__room.rendererInfo())},null,2));
await browser.close();
