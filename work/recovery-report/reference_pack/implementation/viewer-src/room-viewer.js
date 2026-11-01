import * as THREE from 'three';
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js';
import {MeshoptDecoder} from 'meshoptimizer';

const $=id=>document.getElementById(id);
const canvas=$('view'),stage=$('stage');
const renderer=new THREE.WebGLRenderer({canvas,antialias:true,alpha:false,powerPreference:'high-performance'});
renderer.setPixelRatio(Math.min(devicePixelRatio,1.25));
renderer.setClearColor(0x141b23);renderer.outputColorSpace=THREE.SRGBColorSpace;
renderer.localClippingEnabled=true;
const scene=new THREE.Scene(),camera=new THREE.PerspectiveCamera(75,1,.025,100);
camera.up.set(0,1,0);
scene.add(new THREE.HemisphereLight(0xffffff,0x6c7890,2));
const light=new THREE.DirectionalLight(0xffffff,2);light.position.set(3,8,5);scene.add(light);
const keys=new Set(),velocity=new THREE.Vector3(),wheelVelocity=new THREE.Vector3();
const forward=new THREE.Vector3(),right=new THREE.Vector3(),euler=new THREE.Euler(0,0,0,'YXZ');
let data,model,mode='walk',yaw=0,pitch=0,speed=1.2,drag=null,ready=false,dirty=true;
let recorded=null,comparison=false,cutaway=false,shaded=false;
let orbit={target:new THREE.Vector3(),theta:0,phi:1,radius:8};
const clipRoof=new THREE.Plane(new THREE.Vector3(0,-1,0),1.5);
let forceRender=false,frames=[],last=performance.now(),renderCount=0;

function invalidate(){dirty=true;}
function release(){keys.clear();velocity.set(0,0,0);wheelVelocity.set(0,0,0);drag=null;}
function focus(){canvas.focus({preventScroll:true});}
function angles(){camera.getWorldDirection(forward);yaw=Math.atan2(-forward.x,-forward.z);pitch=Math.asin(THREE.MathUtils.clamp(forward.y,-1,1));}
function orient(){euler.set(pitch,yaw,0,'YXZ');camera.quaternion.setFromEuler(euler);camera.up.set(0,1,0);}
function clearRecorded(){recorded=null;if(comparison)setCompare(false);$('views').selectedIndex=0;camera.fov=75;resize();}
function updateClipping(){
  if(!model)return;
  model.traverse(o=>{if(o.isMesh){for(const m of (Array.isArray(o.material)?o.material:[o.material])){
    m.clippingPlanes=cutaway?[clipRoof]:[];m.needsUpdate=true;
  }}});invalidate();
  $('cutaway').setAttribute('aria-pressed',String(cutaway));
}
function updateMode(){
  $('walk').setAttribute('aria-pressed',String(mode==='walk'));
  $('orbit').setAttribute('aria-pressed',String(mode==='orbit'));
  $('hint').textContent=mode==='walk'?'Drag to look · WASD move · Q/E down/up · Shift faster · Wheel step · R reset':'Drag to orbit · Right-drag to pan · Wheel zoom · WASD pan · R reset';
}
function home(){
  if(!ready)return;release();recorded=null;comparison=false;$('source').hidden=true;stage.classList.remove('compare');
  camera.position.fromArray(data.startCamera.position);camera.quaternion.fromArray(data.startCamera.quaternion);
  if(data.homeTarget)camera.lookAt(new THREE.Vector3().fromArray(data.homeTarget));
  angles();pitch=0;orient();mode='walk';cutaway=false;updateClipping();updateMode();
  $('views').selectedIndex=0;$('compare').setAttribute('aria-pressed','false');camera.fov=75;resize();invalidate();
}
function orbitCamera(){
  const {radius:r,phi:p,theta:t,target}=orbit;
  camera.position.set(r*Math.sin(p)*Math.sin(t),r*Math.cos(p),r*Math.sin(p)*Math.cos(t)).add(target);
  camera.up.set(0,1,0);camera.lookAt(target);angles();invalidate();
}
function setMode(next){
  if(!ready)return;release();clearRecorded();mode=next;
  if(next==='orbit'){
    camera.fov=42;camera.updateProjectionMatrix();
    const b=data.bounds;orbit.target.set((b[0][0]+b[1][0])/2,.8,(b[0][2]+b[1][2])/2);
    const span=Math.hypot(b[1][0]-b[0][0],b[1][2]-b[0][2]);orbit.radius=span*.76;orbit.theta=.7;orbit.phi=.85;
    cutaway=true;orbitCamera();
  }else{if(camera.position.y>3.3||camera.position.y<.15)home();angles();orient();cutaway=false;}
  updateClipping();updateMode();invalidate();
}
function top(){setMode('orbit');orbit.phi=.001;orbitCamera();focus();}
function rotate(){
  clearRecorded();release();
  if(mode==='orbit'){orbit.theta+=Math.PI/2;orbitCamera();}
  else{yaw+=Math.PI/2;orient();invalidate();}focus();
}
function preset(index){
  const c=data.presets[index];if(!c)return;
  release();recorded=c;camera.position.fromArray(c.position);camera.quaternion.fromArray(c.quaternion);
  camera.up.set(0,1,0);angles();mode='walk';cutaway=false;updateClipping();updateMode();
  $('views').value=String(index);$('source-frame').src=window.ROOM_EMBED?.sources?.[c.name]||c.source;
  $('source-label').textContent=c.label+' · '+c.name;resize();invalidate();
}
function setCompare(value){
  if(!ready)return;
  if(value&&!recorded){let nearest=0,distance=Infinity;data.presets.forEach((c,i)=>{const d=camera.position.distanceToSquared(new THREE.Vector3().fromArray(c.position));if(d<distance){distance=d;nearest=i;}});preset(nearest);}
  comparison=value;stage.classList.toggle('compare',value);$('source').hidden=!value;
  $('compare').setAttribute('aria-pressed',String(value));resize();invalidate();
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
  const w=canvas.clientWidth,h=canvas.clientHeight;if(!w||!h)return;
  renderer.setSize(w,h,false);camera.aspect=w/h;camera.updateProjectionMatrix();
  if(recorded)calibratedProjection(recorded);invalidate();
}
new ResizeObserver(resize).observe(stage);
window.addEventListener('resize',resize);
window.addEventListener('blur',release);
document.addEventListener('visibilitychange',()=>{if(document.hidden)release();});
canvas.addEventListener('contextmenu',e=>e.preventDefault());
canvas.addEventListener('pointerdown',e=>{
  if(!ready)return;clearRecorded();focus();canvas.setPointerCapture(e.pointerId);
  drag={id:e.pointerId,x:e.clientX,y:e.clientY,pan:e.button===2||e.shiftKey};e.preventDefault();
});
canvas.addEventListener('pointermove',e=>{
  if(!drag||drag.id!==e.pointerId)return;
  const dx=e.clientX-drag.x,dy=e.clientY-drag.y;drag.x=e.clientX;drag.y=e.clientY;
  if(mode==='walk'){
    if(drag.pan){right.set(Math.cos(yaw),0,-Math.sin(yaw));camera.position.addScaledVector(right,-dx*.003);camera.position.y+=dy*.003;}
    else{yaw-=dx*.003;pitch=THREE.MathUtils.clamp(pitch-dy*.003,-1.45,1.45);orient();}
  }else if(drag.pan){right.set(Math.cos(orbit.theta),0,-Math.sin(orbit.theta));orbit.target.addScaledVector(right,-dx*orbit.radius*.001);orbit.target.y+=dy*orbit.radius*.001;orbitCamera();}
  else{orbit.theta-=dx*.004;orbit.phi=THREE.MathUtils.clamp(orbit.phi-dy*.004,.001,1.55);orbitCamera();}
  invalidate();
});
for(const event of ['pointerup','pointercancel','lostpointercapture'])canvas.addEventListener(event,()=>{drag=null;});
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
  const f=Number(keys.has('KeyW'))-Number(keys.has('KeyS')),s=Number(keys.has('KeyD'))-Number(keys.has('KeyA'));
  const y=Number(keys.has('KeyE')||keys.has('Space'))-Number(keys.has('KeyQ')||keys.has('KeyC'));
  const desired=new THREE.Vector3().addScaledVector(forward,f).addScaledVector(right,s);desired.y=y;
  if(desired.lengthSq()>1)desired.normalize();desired.multiplyScalar(speed*(keys.has('ShiftLeft')||keys.has('ShiftRight')?2.7:1));
  velocity.lerp(desired,1-Math.exp(-22*dt));
  if(!keys.size&&velocity.lengthSq()<.00001)velocity.set(0,0,0);
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
  if(ready)step(dt);
  if(ready&&(dirty||forceRender)){render();dirty=false;frames.push(dt*1000);if(frames.length>2400)frames.shift();}
  requestAnimationFrame(loop);
}
requestAnimationFrame(loop);
$('reset').onclick=()=>{home();focus();};$('top').onclick=top;$('rotate').onclick=rotate;
$('walk').onclick=()=>{setMode('walk');focus();};$('orbit').onclick=()=>{setMode('orbit');focus();};
$('cutaway').onclick=()=>{cutaway=!cutaway;updateClipping();focus();};
$('speed').onchange=()=>{speed=Number($('speed').value);focus();};
$('views').onchange=()=>{if($('views').value!=='')preset(Number($('views').value));focus();};
$('compare').onclick=()=>{setCompare(!comparison);focus();};
$('shade').onclick=()=>{
  shaded=!shaded;model.traverse(o=>{if(!o.isMesh)return;
    if(!o.userData.original)o.userData.original=o.material;
    if(shaded){const mat=o.userData.original;o.material=new THREE.MeshStandardMaterial({map:mat.map,side:THREE.DoubleSide,roughness:1,clippingPlanes:mat.clippingPlanes});}
    else{o.material.dispose();o.material=o.userData.original;}
  });$('shade').setAttribute('aria-pressed',String(shaded));invalidate();focus();
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
async function load(){try{
  data=window.ROOM_EMBED?.cameras||await fetch('cameras.json').then(r=>{if(!r.ok)throw Error('Camera metadata missing');return r.json();});
  for(const [i,c]of data.presets.entries()){$('views').add(new Option(c.label,String(i)));}
  let buffer;
  if(window.ROOM_EMBED){
    if(window.ROOM_EMBED.modelChunks){
      const bytes=new Uint8Array(window.ROOM_EMBED.modelByteLength);let offset=0;
      for(const chunk of window.ROOM_EMBED.modelChunks){const raw=atob(chunk);if(offset+raw.length>bytes.length)throw Error('Embedded room length exceeds metadata');for(let i=0;i<raw.length;i++)bytes[offset+i]=raw.charCodeAt(i);offset+=raw.length;}
      if(offset!==bytes.length)throw Error('Embedded room is incomplete');window.ROOM_EMBED.modelChunks.length=0;buffer=bytes.buffer;
    }else{const raw=atob(window.ROOM_EMBED.model);buffer=new Uint8Array(raw.length);for(let i=0;i<raw.length;i++)buffer[i]=raw.charCodeAt(i);buffer=buffer.buffer;}
  }
  else{
    const modelPath=new URLSearchParams(location.search).get('model')||'models/iphone-full-room.glb';
    if(!/^models\/[a-zA-Z0-9_.-]+\.glb$/.test(modelPath))throw Error('Invalid local model path');
    buffer=await fetch(modelPath).then(r=>{if(!r.ok)throw Error('Room model missing');return r.arrayBuffer();});
  }
  const gltf=await new GLTFLoader().setMeshoptDecoder(MeshoptDecoder).parseAsync(buffer,'');model=gltf.scene;scene.add(model);
  ready=true;home();if(new URLSearchParams(location.search).get('mode')==='orbit')setMode('orbit');$('loading').hidden=true;
  $('stats').textContent=`${(data.triangles/1e6).toFixed(2)}M triangles · ${(data.fileBytes/1e6).toFixed(1)} MB`;
  $('quality').textContent=data.qualityMessage||'Floor aligned · approximate metres · doorway aligned from depth, not surveyed';
}catch(error){$('loading').textContent='Could not load the room: '+error.message;console.error(error);}}
load();
