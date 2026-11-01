import {build} from 'esbuild';
import {chromium} from 'playwright';
import {mkdir,writeFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
const root=new URL('../',import.meta.url),out=new URL('analysis/missing-mesh-diagnosis/',root);
await mkdir(out,{recursive:true});
const code=`
import * as T from 'three';
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js';
const renderer=new T.WebGLRenderer({antialias:true,preserveDrawingBuffer:true});
renderer.setSize(1400,1100);renderer.setPixelRatio(1);renderer.setClearColor(0x232a32);renderer.localClippingEnabled=true;
document.body.style.margin='0';document.body.append(renderer.domElement);
const scene=new T.Scene(), camera=new T.OrthographicCamera(-7.9,7.9,6.21,-6.21,.05,100);
camera.position.set(12,15,12);camera.up.set(0,1,0);camera.lookAt(0,.5,0);
const loader=new GLTFLoader(), frame=await fetch('/analysis/fixed-transforms.json').then(r=>r.json());
function prepare(root){root.traverse(o=>{if(o.isMesh){const old=o.material;o.material=new T.MeshBasicMaterial({map:old.map,color:old.color,side:T.DoubleSide});}});}
function render(floor){scene.traverse(o=>{if(o.isMesh)o.material.clippingPlanes=[new T.Plane(new T.Vector3(0,-1,0),1.5),...(floor?[new T.Plane(new T.Vector3(0,1,0),.10)]:[])];});renderer.render(scene,camera);renderer.getContext().finish();}
function clear(){scene.traverse(o=>{if(o.isMesh){o.geometry.dispose();o.material.map?.dispose();o.material.dispose();}});scene.clear();window.gc?.();}
window.diagnose={async variant(kind,floor=false){clear();
 if(kind==='final'){const g=await loader.loadAsync('/exports/iphone-full-room.glb');prepare(g.scene);scene.add(g.scene);}
 else{for(let z=0;z<3;z++){
  const path=kind==='original'?'/exports/zone-'+z+'/zone-'+z+'-clean.glb':'/exports/optimized-m12/zone-'+z+'/zone-'+z+'.glb';
  const g=await loader.loadAsync(path);prepare(g.scene);const t=frame.zones['zone-'+z],s=t.scale,r=t.R;
  g.scene.matrixAutoUpdate=false;g.scene.matrix.set(s*r[0][0],s*r[0][1],s*r[0][2],t.t[0],s*r[1][0],s*r[1][1],s*r[1][2],t.t[1],s*r[2][0],s*r[2][1],s*r[2][2],t.t[2],0,0,0,1);scene.add(g.scene);
 }}render(floor);return {triangles:renderer.info.render.triangles,calls:renderer.info.render.calls};
},floor(value){render(value);return true;}};
window.ready=true;
`;
await build({stdin:{contents:code,resolveDir:process.cwd(),sourcefile:'diagnose-entry.js'},outfile:fileURLToPath(new URL('diagnostic.bundle.js',out)),bundle:true,format:'esm',minify:true,logLevel:'silent'});
await writeFile(new URL('viewer.html',out),'<!doctype html><meta charset="utf-8"><script type="module" src="diagnostic.bundle.js"></script>');
const browser=await chromium.launchPersistentContext(fileURLToPath(new URL('profile/',out)),{executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true,viewport:{width:1400,height:1100},deviceScaleFactor:1,args:['--enable-gpu','--use-angle=d3d11','--js-flags=--expose-gc']});
try{
 const page=browser.pages()[0];page.on('pageerror',e=>console.log('PAGE ERROR',String(e)));
 await page.goto('http://127.0.0.1:53252/analysis/missing-mesh-diagnosis/viewer.html');
 await page.waitForFunction(()=>window.ready,null,{timeout:30000});
 const results=[];
 for(const [kind,name]of [['original','01-original-untrimmed'],['compact','02-compact-untrimmed'],['final','03-final-no-display-floor-clip']]){
  const result=await page.evaluate(async kind=>await diagnose.variant(kind,false),kind);
  await page.screenshot({path:fileURLToPath(new URL(name+'.png',out))});results.push({name,...result});console.log(name,JSON.stringify(result));
 }
 await page.evaluate(()=>diagnose.floor(true));
 await page.screenshot({path:fileURLToPath(new URL('04-final-with-display-floor-clip.png',out))});
 await writeFile(new URL('render-info.json',out),JSON.stringify(results,null,2));
}finally{await browser.close();}
