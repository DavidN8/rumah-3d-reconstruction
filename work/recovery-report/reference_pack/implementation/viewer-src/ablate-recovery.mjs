import {chromium} from 'playwright';
import {spawn} from 'node:child_process';
import {mkdir,writeFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
const root=new URL('../',import.meta.url),stage=process.argv[2]||'raw',out=new URL(`recovery-v2/analysis/seam-ablation-${stage}/`,root);
await mkdir(out,{recursive:true});
const server=spawn('C:/Python314/python.exe',['-m','http.server','53253','--bind','127.0.0.1','--directory',fileURLToPath(root)],{windowsHide:true,stdio:'ignore'});
let browser;
try{
 for(let i=0;i<30;i++){try{if((await fetch('http://127.0.0.1:53253/recovery-v2/analysis/original-components.json')).ok)break;}catch{}await new Promise(r=>setTimeout(r,200));}
 browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true,args:['--enable-gpu','--use-angle=d3d11']});
 const page=await browser.newPage({viewport:{width:1440,height:1000}}),records=[];
 await page.goto(`http://127.0.0.1:53253/recovery-v2/review/${stage}/`);await page.waitForFunction(()=>window.__room?.ready,null,{timeout:120000});
 await page.selectOption('#views','2');await page.click('#compare');
 for(const [label,values] of [['both',[true,true]],['kitchen-only',[true,false]],['living-only',[false,true]]]){
  const components=await page.evaluate(v=>__room.componentVisibility(v),values);await page.waitForTimeout(200);await page.screenshot({path:fileURLToPath(new URL('frame-1398-'+label+'.png',out))});records.push({label,components});
 }
 await writeFile(new URL('records.json',out),JSON.stringify(records,null,2));console.log(records);
}finally{if(browser)await browser.close();server.kill();}
