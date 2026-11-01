import * as THREE from 'three';
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js';
import {MeshoptDecoder} from 'meshoptimizer';
import {chooseQuality,readModel,pinchRatio,withDeadline} from './loader-core.js';

const $=id=>document.getElementById(id);
const canvas=$('view'),stage=$('stage');
const params=new URLSearchParams(location.search),manifestPath='__MANIFEST__';
const deviceSignals={requested:params.get('quality'),coarse:matchMedia('(pointer:coarse)').matches,touchPoints:navigator.maxTouchPoints,width:innerWidth,userAgent:navigator.userAgent};
let phoneInput=chooseQuality({...deviceSignals,requested:null})==='phone';
document.body.classList.toggle('phone',phoneInput);document.body.classList.toggle('debug',params.get('debug')==='1');
let renderer,rendererError;
try{renderer=new THREE.WebGLRenderer({canvas,antialias:!phoneInput,alpha:true,powerPreference:'high-performance'});
renderer.setPixelRatio(Math.min(devicePixelRatio,phoneInput?1:1.25));
renderer.setClearColor(0x141b23,1);renderer.outputColorSpace=THREE.SRGBColorSpace;}
catch(error){rendererError=error;}
const scene=new THREE.Scene(),camera=new THREE.PerspectiveCamera(75,1,.025,100);
camera.up.set(0,1,0);
scene.add(new THREE.HemisphereLight(0xffffff,0x6c7890,2));
const light=new THREE.DirectionalLight(0xffffff,2);light.position.set(3,8,5);scene.add(light);
const keys=new Set(),velocity=new THREE.Vector3(),wheelVelocity=new THREE.Vector3();
const forward=new THREE.Vector3(),right=new THREE.Vector3(),euler=new THREE.Euler(0,0,0,'YXZ');
let data,model,mode='walk',yaw=0,pitch=0,speed=1.2,drag=null,ready=false,dirty=true;
let recorded=null,comparison=false,seeInside=false,shaded=false;
let orbit={target:new THREE.Vector3(),theta:0,phi:1,radius:8};
let framingPoints=new Float32Array();
let forceRender=false,frames=[],last=performance.now(),renderCount=0;
let manifest,manifestPromise,currentQuality,asset,loadGeneration=0,downloadAbort,phase='starting',loadStarted=0;
let downloadBytes=0,preparedMs=0,modelDiagnostics={},idleTimer,totalTimer,metadataReady=false;
const pointers=new Map(),touchMoves=new Map();
let gesture=null;

function invalidate(){dirty=true;}
function release(){keys.clear();touchMoves.clear();pointers.clear();gesture=null;velocity.set(0,0,0);wheelVelocity.set(0,0,0);drag=null;}
function focus(){canvas.focus({preventScroll:true});}
function angles(){camera.getWorldDirection(forward);yaw=Math.atan2(-forward.x,-forward.z);pitch=Math.asin(THREE.MathUtils.clamp(forward.y,-1,1));}
function orient(){euler.set(pitch,yaw,0,'YXZ');camera.quaternion.setFromEuler(euler);camera.up.set(0,1,0);}
function clearRecorded(){recorded=null;if(comparison)setCompare(false);$('views').selectedIndex=0;camera.fov=mode==='orbit'?42:75;resize();}
function updateSurface(){
  if(!model)return;
  model.traverse(o=>{if(o.isMesh){for(const m of (Array.isArray(o.material)?o.material:[o.material])){
    // Open the exterior by back-face culling. Never slice cabinets, frames or walls by height.
    m.clippingPlanes=[];m.side=seeInside?THREE.FrontSide:THREE.DoubleSide;m.needsUpdate=true;
  }}});invalidate();
  $('see-inside').setAttribute('aria-pressed',String(seeInside));
}
function updateMode(){
  $('walk').setAttribute('aria-pressed',String(mode==='walk'));
  $('orbit').setAttribute('aria-pressed',String(mode==='orbit'));
  $('touch-controls').classList.toggle('walking',ready&&mode==='walk'&&!comparison);
  $('hint').textContent=phoneInput?(mode==='walk'?'Drag to look · Hold arrows to walk · Pinch to move':'Drag to orbit · Pinch to zoom · Two fingers to pan'):(mode==='walk'?'Drag to look · WASD move · Q/E down/up · Wheel step':'Drag to orbit · Right-drag to pan · Wheel zoom · WASD pan');
}
function home(){
  if(!ready)return;release();recorded=null;comparison=false;$('source').hidden=true;stage.classList.remove('compare');
  camera.position.fromArray(data.startCamera.position);camera.quaternion.fromArray(data.startCamera.quaternion);
  if(data.homeTarget)camera.lookAt(new THREE.Vector3().fromArray(data.homeTarget));
  angles();pitch=0;orient();mode='walk';seeInside=false;updateSurface();updateMode();
  $('views').selectedIndex=0;$('compare').setAttribute('aria-pressed','false');camera.fov=75;resize();invalidate();
}
function orbitCamera(){
  const {radius:r,phi:p,theta:t,target}=orbit;
  camera.position.set(r*Math.sin(p)*Math.sin(t),r*Math.cos(p),r*Math.sin(p)*Math.cos(t)).add(target);
  camera.up.set(0,1,0);camera.lookAt(target);angles();invalidate();
}
function fittedOrbitRadius(aspect=camera.aspect){
  const b=data.bounds,center=new THREE.Vector3().fromArray(b[0]).add(new THREE.Vector3().fromArray(b[1])).multiplyScalar(.5);
  const direction=new THREE.Vector3(Math.sin(orbit.phi)*Math.sin(orbit.theta),Math.cos(orbit.phi),Math.sin(orbit.phi)*Math.cos(orbit.theta));
  const horizontal=new THREE.Vector3(Math.cos(orbit.theta),0,-Math.sin(orbit.theta));
  const vertical=new THREE.Vector3().crossVectors(direction,horizontal);
  const tangent=Math.tan(THREE.MathUtils.degToRad(camera.fov/2));let radius=.3;
  const point=new THREE.Vector3();
  for(let i=0;i<framingPoints.length;i+=3){
    point.fromArray(framingPoints,i).sub(center);const depth=point.dot(direction);
    radius=Math.max(radius,depth+1.12*Math.abs(point.dot(horizontal))/(tangent*aspect),depth+1.12*Math.abs(point.dot(vertical))/tangent);
  }
  return radius;
}
function setMode(next){
  if(!ready)return;release();clearRecorded();mode=next;
  if(next==='orbit'){
    camera.fov=42;camera.updateProjectionMatrix();
    const b=data.bounds;orbit.target.fromArray(b[0]).add(new THREE.Vector3().fromArray(b[1])).multiplyScalar(.5);
    orbit.theta=.7;orbit.phi=.85;orbit.radius=fittedOrbitRadius();
    seeInside=true;orbitCamera();
  }else{camera.fov=75;camera.updateProjectionMatrix();if(camera.position.y>3.3||camera.position.y<.15)home();angles();orient();seeInside=false;}
  updateSurface();updateMode();invalidate();
}
function top(){setMode('orbit');orbit.phi=.001;orbit.radius=fittedOrbitRadius();orbitCamera();focus();}
function rotate(){
  clearRecorded();release();
  if(mode==='orbit'){const zoom=orbit.radius/fittedOrbitRadius();orbit.theta+=Math.PI/2;orbit.radius=fittedOrbitRadius()*zoom;orbitCamera();}
  else{yaw+=Math.PI/2;orient();invalidate();}focus();
}
function preset(index){
  const c=data.presets[index];if(!c)return;
  release();recorded=c;camera.position.fromArray(c.position);camera.quaternion.fromArray(c.quaternion);
  camera.up.set(0,1,0);angles();mode='walk';seeInside=false;updateSurface();updateMode();
  $('views').value=String(index);$('source-frame').src=c.source;
  $('source-label').textContent=c.label+' · '+c.name;resize();invalidate();
}
function setCompare(value){
  if(!ready)return;
  if(value&&!recorded){let nearest=0,distance=Infinity;data.presets.forEach((c,i)=>{const d=camera.position.distanceToSquared(new THREE.Vector3().fromArray(c.position));if(d<distance){distance=d;nearest=i;}});preset(nearest);}
  comparison=value;stage.classList.toggle('compare',value);$('source').hidden=!value;
  $('compare').setAttribute('aria-pressed',String(value));updateMode();resize();invalidate();
}
function calibratedProjection(c){
  const [fx,fy,cx,cy]=c.intrinsics,w=c.imageWidth,h=c.imageHeight,n=camera.near;
  camera.projectionMatrix.makePerspective(-cx/fx*n,(w-cx)/fx*n,cy/fy*n,-(h-cy)/fy*n,n,camera.far);
  camera.projectionMatrixInverse.copy(camera.projectionMatrix).invert();
}
function viewport(){
  const w=canvas.clientWidth,h=canvas.clientHeight;
  if(recorded){const ratio=recorded.imageWidth/recorded.imageHeight,ww=Math.min(w,h*ratio),hh=ww/ratio;
    return {x:(w-ww)/2,y:(h-hh)/2,w:ww,h:hh};}
  return {x:0,y:0,w,h};
}
function resize(){
  if(!renderer)return;
  const w=canvas.clientWidth,h=canvas.clientHeight;if(!w||!h)return;
  if(ready&&mode==='orbit'&&!recorded){orbit.radius*=fittedOrbitRadius(w/h)/fittedOrbitRadius(camera.aspect);orbitCamera();}
  renderer.setSize(w,h,false);camera.aspect=w/h;camera.updateProjectionMatrix();
  if(recorded)calibratedProjection(recorded);invalidate();
}
const observer=new ResizeObserver(resize);observer.observe(stage);observer.observe(canvas);
window.addEventListener('resize',()=>{phoneInput=chooseQuality({...deviceSignals,requested:null,width:innerWidth})==='phone';document.body.classList.toggle('phone',phoneInput);resize();updateMode();});
window.addEventListener('blur',release);
document.addEventListener('visibilitychange',()=>{if(document.hidden)release();});
canvas.addEventListener('contextmenu',e=>e.preventDefault());
canvas.addEventListener('pointerdown',e=>{
  if(!ready)return;clearRecorded();focus();canvas.setPointerCapture(e.pointerId);
  pointers.set(e.pointerId,{x:e.clientX,y:e.clientY});
  if(pointers.size>1){gesture=gestureState();drag=null;e.preventDefault();return;}
  drag={id:e.pointerId,x:e.clientX,y:e.clientY,pan:e.button===2||e.shiftKey};e.preventDefault();
});
canvas.addEventListener('pointermove',e=>{
  if(pointers.has(e.pointerId))pointers.set(e.pointerId,{x:e.clientX,y:e.clientY});
  if(pointers.size>1){
    const next=gestureState();
    if(gesture){zoom(pinchRatio(gesture.distance,next.distance));pan(next.x-gesture.x,next.y-gesture.y);}
    gesture=next;e.preventDefault();return;
  }
  if(!drag||drag.id!==e.pointerId)return;
  const dx=e.clientX-drag.x,dy=e.clientY-drag.y;drag.x=e.clientX;drag.y=e.clientY;
  if(mode==='walk'){
    if(drag.pan){right.set(Math.cos(yaw),0,-Math.sin(yaw));camera.position.addScaledVector(right,-dx*.003);camera.position.y+=dy*.003;}
    else{yaw-=dx*.003;pitch=THREE.MathUtils.clamp(pitch-dy*.003,-1.45,1.45);orient();}
  }else if(drag.pan){right.set(Math.cos(orbit.theta),0,-Math.sin(orbit.theta));orbit.target.addScaledVector(right,-dx*orbit.radius*.001);orbit.target.y+=dy*orbit.radius*.001;orbitCamera();}
  else{orbit.theta-=dx*.004;orbit.phi=THREE.MathUtils.clamp(orbit.phi-dy*.004,.001,1.55);orbitCamera();}
  invalidate();
});
for(const event of ['pointerup','pointercancel','lostpointercapture'])canvas.addEventListener(event,e=>{pointers.delete(e.pointerId);drag=null;gesture=null;});
canvas.addEventListener('wheel',e=>{
  if(!ready)return;e.preventDefault();clearRecorded();
  const dy=THREE.MathUtils.clamp(e.deltaY*(e.deltaMode===1?16:1),-120,120);
  if(mode==='walk'){forward.set(-Math.sin(yaw),0,-Math.cos(yaw));wheelVelocity.addScaledVector(forward,-dy*.022*speed);}
  else{orbit.radius=THREE.MathUtils.clamp(orbit.radius*Math.exp(dy*.001),.3,80);orbitCamera();}invalidate();
},{passive:false});
const movement=new Set(['KeyW','KeyS','KeyA','KeyD','KeyQ','KeyE','Space','KeyC']);
window.addEventListener('keydown',e=>{
  if(!ready||e.ctrlKey||e.metaKey||e.altKey||e.target.closest?.('select,input,button,a'))return;
  if(e.code==='Escape'){release();return;}
  if(e.code==='KeyR'){e.preventDefault();home();return;}
  if(!movement.has(e.code)&&!['ShiftLeft','ShiftRight'].includes(e.code))return;
  e.preventDefault();if(!keys.size){angles();clearRecorded();orient();}keys.add(e.code);invalidate();
});
window.addEventListener('keyup',e=>{keys.delete(e.code);});
function step(dt){
  forward.set(-Math.sin(yaw),0,-Math.cos(yaw));right.set(Math.cos(yaw),0,-Math.sin(yaw));
  const touch=new Set(touchMoves.values());
  const f=Number(keys.has('KeyW')||touch.has('forward'))-Number(keys.has('KeyS')||touch.has('back')),s=Number(keys.has('KeyD')||touch.has('right'))-Number(keys.has('KeyA')||touch.has('left'));
  const y=Number(keys.has('KeyE')||keys.has('Space')||touch.has('up'))-Number(keys.has('KeyQ')||keys.has('KeyC')||touch.has('down'));
  const desired=new THREE.Vector3().addScaledVector(forward,f).addScaledVector(right,s);desired.y=y;
  if(desired.lengthSq()>1)desired.normalize();desired.multiplyScalar(speed*(keys.has('ShiftLeft')||keys.has('ShiftRight')?2.7:1));
  velocity.lerp(desired,1-Math.exp(-22*dt));
  if(!keys.size&&!touchMoves.size&&velocity.lengthSq()<.00001)velocity.set(0,0,0);
  const delta=velocity.clone().add(wheelVelocity).multiplyScalar(dt);
  wheelVelocity.multiplyScalar(Math.exp(-12*dt));
  if(delta.lengthSq()>1e-10){
    if(mode==='walk')camera.position.add(delta);
    else{orbit.target.add(delta);orbitCamera();}invalidate();
  }
}
function render(){
  const v=viewport();renderer.setScissorTest(false);renderer.setViewport(0,0,canvas.clientWidth,canvas.clientHeight);renderer.clear();
  renderer.setViewport(v.x,v.y,v.w,v.h);renderer.render(scene,camera);
  // Verification waits for GPU completion; normal navigation stays asynchronous.
  if(forceRender)renderer.getContext().finish();
  renderCount++;
}
function loop(now){
  const dt=Math.min((now-last)/1000,.05);last=now;
  if(ready&&phase==='ready')step(dt);
  if(ready&&phase==='ready'&&(dirty||forceRender)){try{render();dirty=false;frames.push(dt*1000);if(frames.length>2400)frames.shift();updateDiagnostics();}catch(error){showFailure(error);}}
  requestAnimationFrame(loop);
}
requestAnimationFrame(loop);
$('reset').onclick=()=>{home();focus();};$('top').onclick=top;$('rotate').onclick=rotate;
$('walk').onclick=()=>{setMode('walk');focus();};$('orbit').onclick=()=>{setMode('orbit');focus();};
$('see-inside').onclick=()=>{seeInside=!seeInside;updateSurface();focus();};
$('speed').onchange=()=>{speed=Number($('speed').value);focus();};
$('views').onchange=()=>{if($('views').value!=='')preset(Number($('views').value));focus();};
$('compare').onclick=()=>{setCompare(!comparison);focus();};
$('shade').onclick=()=>{
  shaded=!shaded;model.traverse(o=>{if(!o.isMesh)return;
    if(!o.userData.original)o.userData.original=o.material;
    if(shaded){const mat=o.material;o.material=new THREE.MeshStandardMaterial({map:mat.map,side:mat.side,roughness:1,clippingPlanes:[]});}
    else{o.material.dispose();o.material=o.userData.original;}
  });updateSurface();$('shade').setAttribute('aria-pressed',String(shaded));invalidate();focus();
};

window.__room={get ready(){return ready;},get data(){return data;},preset,home,top,rotate,setMode,
  state(){const f=new THREE.Vector3();camera.getWorldDirection(f);return {position:camera.position.toArray(),quaternion:camera.quaternion.toArray(),
    forward:f.toArray(),up:camera.up.toArray(),right:new THREE.Vector3(1,0,0).applyQuaternion(camera.quaternion).toArray(),mode,yaw,pitch,
    keys:[...keys],comparison,recorded:recorded?.name,triangles:renderer.info.render.triangles,renderCount};},
  benchmark(value){forceRender=value;frames=[];return true;},timings(){return [...frames];},
  componentVisibility(values){model.children.forEach((o,i)=>{o.visible=values[i]!==false;});invalidate();return model.children.map(o=>({name:o.name,visible:o.visible}));},
  rendererInfo(){const gl=renderer.getContext(),info=gl.getExtension('WEBGL_debug_renderer_info');return {renderer:info?gl.getParameter(info.UNMASKED_RENDERER_WEBGL):'unavailable',drawCalls:renderer.info.render.calls,triangles:renderer.info.render.triangles};},
  snapshot(){render();return canvas.toDataURL('image/png');}
};
function gestureState(){const [a,b]=[...pointers.values()];return {x:(a.x+b.x)/2,y:(a.y+b.y)/2,distance:Math.hypot(a.x-b.x,a.y-b.y)};}
function zoom(ratio){
  if(!ready)return;
  if(mode==='orbit'){orbit.radius=THREE.MathUtils.clamp(orbit.radius*ratio,.3,80);orbitCamera();}
  else{camera.getWorldDirection(forward);camera.position.addScaledVector(forward,(1-ratio)*2);invalidate();}
}
function pan(dx,dy){
  const factor=(mode==='orbit'?orbit.radius:3)*.0017;
  right.set(1,0,0).applyQuaternion(camera.quaternion);
  const up=new THREE.Vector3(0,1,0).applyQuaternion(camera.quaternion);
  const target=mode==='orbit'?orbit.target:camera.position;
  target.addScaledVector(right,-dx*factor).addScaledVector(up,dy*factor);
  if(mode==='orbit')orbitCamera();else invalidate();
}
for(const button of document.querySelectorAll('[data-move]')){
  button.addEventListener('pointerdown',e=>{if(!ready||mode!=='walk')return;e.preventDefault();button.setPointerCapture(e.pointerId);touchMoves.set(e.pointerId,button.dataset.move);invalidate();});
  for(const event of ['pointerup','pointercancel','lostpointercapture'])button.addEventListener(event,e=>{touchMoves.delete(e.pointerId);invalidate();});
}
$('zoom-in').onclick=()=>{clearRecorded();zoom(.82);};$('zoom-out').onclick=()=>{clearRecorded();zoom(1/.82);};
$('more').onclick=()=>{const open=$('extra').classList.toggle('open');$('more').setAttribute('aria-expanded',String(open));resize();};
$('quality').onchange=()=>loadAsset($('quality').value);
$('retry').onclick=$('recover-phone').onclick=()=>{const url=new URL(location.href);url.searchParams.set('quality','phone');url.searchParams.set('v','20261029');location.assign(url.href);};
$('cancel-load').onclick=()=>loadAsset('phone');
async function showGallery(){
  try{await loadMetadata();const c=data.presets[Number($('gallery-view').value)||0];$('gallery-photo').src=c.source;$('gallery-caption').textContent=c.label+' · '+c.name;if(!$('gallery').open)$('gallery').showModal();release();}
  catch(error){$('load-status').textContent='Photos could not open. Check the connection and try again.';}
}
$('photos').onclick=$('loading-photos').onclick=$('recovery-photos').onclick=showGallery;
$('gallery-view').onchange=showGallery;$('gallery-close').onclick=()=>{$('gallery').close();$('gallery-photo').removeAttribute('src');};

function controlsEnabled(value){for(const button of document.querySelectorAll('[data-3d],[data-move]'))button.disabled=!value;}
function updateDiagnostics(){
  const state={build:'20261029-fullheight-v1',phase,quality:currentQuality||'choosing',phoneInput,downloadBytes,fileBytes:asset?.fileBytes||0,
    triangles:modelDiagnostics.triangles||0,geometryMiB:modelDiagnostics.geometryMiB||0,textures:modelDiagnostics.textures||[],
    preparedSeconds:preparedMs/1000,mode,seeInside,heightClipping:false,renderCount,comparison,recorded:recorded?.name||null,
    position:camera.position.toArray(),activeMoves:[...touchMoves.values()],keys:[...keys],viewport:[canvas.clientWidth,canvas.clientHeight]};
  $('diagnostics').textContent=JSON.stringify(state,null,2);document.body.dataset.phase=phase;document.body.dataset.quality=state.quality;
}
function setPhase(value,message,detail=''){phase=value;$('load-status').textContent=message;$('load-detail').textContent=detail;updateDiagnostics();}
function stopTimers(){clearTimeout(idleTimer);clearTimeout(totalTimer);}
function showFailure(error){
  stopTimers();ready=false;release();controlsEnabled(false);$('touch-controls').classList.remove('walking');$('loading').hidden=false;
  $('load-title').textContent='The room could not finish loading';
  $('retry').hidden=false;$('cancel-load').hidden=true;$('load-progress').hidden=true;
  setPhase('failed',error?.message||'Please retry the phone view or browse the original photos.','The phone view uses much less memory.');
  console.error('Room loading failed',error);
}
function disposeModel(root){
  if(!root)return;
  scene.remove(root);const textures=new Set(),materials=new Set();
  root.traverse(o=>{if(!o.isMesh)return;o.geometry.dispose();for(const m of [...(Array.isArray(o.material)?o.material:[o.material]),...(o.userData.original?[o.userData.original]:[])])if(m){materials.add(m);for(const v of Object.values(m))if(v?.isTexture)textures.add(v);}});
  for(const texture of textures){texture.dispose();texture.source?.data?.close?.();}
  for(const material of materials)material.dispose();renderer?.renderLists.dispose();
}
function inspectModel(root){
  const buffers=new Set(),textures=new Set(),points=[],point=new THREE.Vector3();let bytes=0,triangles=0;
  root.updateMatrixWorld(true);
  root.traverse(o=>{if(!o.isMesh)return;triangles+=(o.geometry.index?.count||o.geometry.attributes.position.count)/3;
    const position=o.geometry.attributes.position,stride=Math.max(1,Math.floor(position.count/20000));
    for(let i=0;i<position.count;i+=stride){point.fromBufferAttribute(position,i).applyMatrix4(o.matrixWorld);points.push(point.x,point.y,point.z);}
    for(const attr of [...Object.values(o.geometry.attributes),o.geometry.index].filter(Boolean)){const buffer=attr.isInterleavedBufferAttribute?attr.data:attr;if(!buffers.has(buffer)){buffers.add(buffer);bytes+=buffer.array.byteLength;}}
    for(const mat of (Array.isArray(o.material)?o.material:[o.material]))if(mat.map)textures.add(mat.map);
  });
  framingPoints=Float32Array.from(points);
  return {triangles,geometryMiB:Math.round(bytes/1024/1024*10)/10,textures:[...textures].map(t=>[t.image.width,t.image.height])};
}
async function loadMetadata(){
  if(metadataReady)return manifest;
  if(!manifestPromise)manifestPromise=(async()=>{
    const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),15000);
    try{const r=await fetch(manifestPath,{signal:controller.signal});if(!r.ok)throw Error('Room details are temporarily unavailable.');manifest=await r.json();data=manifest.cameraData;
      for(const [i,c] of data.presets.entries()){$('views').add(new Option(c.label,String(i)));$('gallery-view').add(new Option(c.label,String(i)));}
      $('quality').disabled=false;metadataReady=true;return manifest;
    }finally{clearTimeout(timer);}
  })().catch(error=>{manifestPromise=null;throw error;});
  return manifestPromise;
}
async function loadAsset(quality){
  const generation=++loadGeneration;downloadAbort?.abort();stopTimers();release();ready=false;controlsEnabled(false);
  disposeModel(model);model=null;framingPoints=new Float32Array();modelDiagnostics={};shaded=false;$('shade').setAttribute('aria-pressed','false');
  $('source').hidden=true;stage.classList.remove('compare');comparison=false;recorded=null;
  currentQuality=quality;downloadBytes=0;preparedMs=0;loadStarted=performance.now();
  $('quality').value=quality;$('loading').hidden=false;$('recovery').hidden=true;$('load-progress').hidden=false;$('load-progress').value=0;
  $('retry').hidden=true;$('cancel-load').hidden=quality!=='native';$('load-title').textContent=quality==='phone'?'Opening the phone view':'Opening the full native model';
  setPhase('details','Opening room details…');
  try{
    await loadMetadata();if(generation!==loadGeneration)return;asset=manifest.models[quality];if(!asset)throw Error('That room view is unavailable.');
    if(!renderer)throw Error('3D graphics could not start on this browser. Try reloading the phone view or use Photos.');
    if(quality==='phone'&&(asset.fileBytes>24*1024*1024||asset.maxTextureSize>2048))throw Error('The phone view is larger than expected. Please refresh and retry.');
    downloadAbort=new AbortController();const controller=downloadAbort;
    let idleExpired=false,totalExpired=false;
    const resetIdle=()=>{clearTimeout(idleTimer);idleTimer=setTimeout(()=>{idleExpired=true;controller.abort();},45000);};
    resetIdle();totalTimer=setTimeout(()=>{totalExpired=true;controller.abort();},quality==='phone'?180000:600000);
    setPhase('downloading','Downloading the room…',`0 / ${(asset.fileBytes/1e6).toFixed(1)} MB`);
    let buffer;
    try{const response=await fetch(asset.url,{signal:controller.signal});
      buffer=await readModel(response,asset.fileBytes,{signal:controller.signal,onProgress:(bytes,total)=>{
        downloadBytes=bytes;resetIdle();$('load-progress').value=Math.min(94,bytes/total*94);
        setPhase('downloading',`Downloading the room · ${Math.round(bytes/total*100)}%`,`${(bytes/1e6).toFixed(1)} / ${(total/1e6).toFixed(1)} MB`);
      }});
    }catch(error){if(idleExpired)throw Error('The connection stopped sending the room. Please retry the phone view.');if(totalExpired)throw Error('The download is taking too long. Retry the phone view or use Photos.');throw error;}
    stopTimers();if(generation!==loadGeneration)return;
    setPhase('preparing','Preparing the 3D room…','The download is complete.');$('load-progress').value=96;
    await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));
    const loader=new GLTFLoader().setMeshoptDecoder(MeshoptDecoder);
    let abandoned=false;
    const parsing=loader.parseAsync(buffer,'').then(gltf=>{if(abandoned||generation!==loadGeneration){disposeModel(gltf.scene);throw new DOMException('Superseded','AbortError');}return gltf;});
    let gltf;
    try{gltf=await withDeadline(parsing,quality==='phone'?30000:90000,'The browser could not prepare this 3D view. Reload the phone view or use Photos.');}
    catch(error){abandoned=true;throw error;}
    buffer=null;
    if(generation!==loadGeneration){disposeModel(gltf.scene);return;}
    model=gltf.scene;scene.add(model);modelDiagnostics=inspectModel(model);
    if(quality==='phone'&&(modelDiagnostics.geometryMiB>64||modelDiagnostics.textures.some(([w,h])=>w>2048||h>2048)))throw Error('The phone view exceeded its graphics budget. Please use Photos and report this message.');
    ready=true;home();if(quality==='phone'||params.get('mode')==='orbit')setMode('orbit');resize();
    setPhase('drawing','Drawing the room…');$('load-progress').value=98;
    await withDeadline(renderer.compileAsync(scene,camera),30000,'The browser could not finish drawing the room. Retry the phone view or use Photos.');
    if(generation!==loadGeneration)return;
    render();if(renderer.getContext().isContextLost())throw Error('3D graphics were interrupted. Please reload the phone view.');
    preparedMs=performance.now()-loadStarted;phase='ready';controlsEnabled(true);$('loading').hidden=true;$('load-progress').value=100;
    $('stats').textContent=`${quality==='phone'?'Phone view':'Full native'} · ${(modelDiagnostics.triangles/1e6).toFixed(2)}M triangles · ${(asset.fileBytes/1e6).toFixed(1)} MB`;
    $('quality-note').textContent=quality==='phone'?'Phone view · full native available in Quality':'Full native · approximate scale';
    updateMode();invalidate();updateDiagnostics();
  }catch(error){if(generation!==loadGeneration)return;showFailure(error);}
}
canvas.addEventListener('webglcontextlost',event=>{event.preventDefault();++loadGeneration;downloadAbort?.abort();showFailure(Error('Your browser interrupted the 3D graphics. Reload the phone view, or use Photos.'));});
canvas.addEventListener('webglcontextrestored',()=>{if(phase==='failed')$('load-detail').textContent='Graphics are available again. Tap Retry phone view.';});
loadAsset(chooseQuality(deviceSignals));
