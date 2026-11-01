import * as THREE from 'three';
import {OrbitControls} from 'three/addons/controls/OrbitControls.js';
import {waitForNativeDraw,nativeSparkFileType} from './production/native-delivery.js';
let renderer,camera,scene,controls,spark,model,metadata,kind,poseIndex=0,busy=false,frame;
const status=document.getElementById('status');
const nearby=new URLSearchParams(location.search).get('set')==='nearby';
const evidence={};
function report(message){status.textContent=message;}
function requestFrame(){if(frame)return;frame=requestAnimationFrame(()=>{frame=null;renderer.render(scene,camera);});}
async function drawStable(){
 scene.updateMatrixWorld(true);camera.updateMatrixWorld(true);
 renderer.render(scene,camera);
 await waitForNativeDraw({update:()=>spark.update({scene,camera}),draw:()=>renderer.render(scene,camera),activeSplats:()=>spark.activeSplats});
 // A second explicitly awaited update ensures a changed pose has a sorted draw.
 await spark.update({scene,camera});renderer.render(scene,camera);
}
async function matchedPose(index){
 if(busy)return;busy=true;document.getElementById('save').disabled=true;
 try{
  poseIndex=index;const p=metadata.presets[index];camera.position.fromArray(p.position);camera.quaternion.fromArray(p.quaternion);camera.updateMatrixWorld(true);
  const [fx,fy,cx,cy]=p.intrinsics,W=p.imageWidth,H=p.imageHeight,n=.02,f=100;
  camera.projectionMatrix.makePerspective(-cx/fx*n,(W-cx)/fx*n,cy/fy*n,-(H-cy)/fy*n,n,f);camera.projectionMatrixInverse.copy(camera.projectionMatrix).invert();
  // Setting the target without controls.update preserves the exact calibrated roll.
  controls.target.copy(camera.position).add(new THREE.Vector3(0,0,-1).applyQuaternion(camera.quaternion));
  document.getElementById('photo').src=kind==='matched'?`/reference/${index}.jpg`:`/${nearby?'bath-nearby-cameras-photos':'clean-cameras-photos'}/${p.sourceFile.replaceAll('\\','/').split('/').pop()}`;
  evidence.pose={index,name:p.name,split:p.split,sourceTimeSeconds:p.sourceTimeSeconds,position:p.position,quaternion:p.quaternion,intrinsics:p.intrinsics};
  if(spark){await drawStable();report(`Ready: ${kind}, camera ${index+1}/${metadata.presets.length}, ${p.label}. Source ${model.numSplats.toLocaleString()} splats; active ${spark.activeSplats.toLocaleString()}.`);}
 }finally{busy=false;document.getElementById('save').disabled=!spark;}
}
export async function open(selected){
 kind=selected;const started=performance.now();report(`Loading ${kind}…`);
 metadata=await(await fetch(kind==='matched'?'/old-to-clean-alignment-matched-new-cameras.json':nearby?'/bath-nearby-cameras.json':'/clean-cameras.json')).json();
 renderer=new THREE.WebGLRenderer({antialias:false,alpha:false,preserveDrawingBuffer:true,powerPreference:'high-performance'});renderer.setPixelRatio(1);renderer.setSize(600,600);renderer.setClearColor(0);renderer.outputColorSpace=THREE.SRGBColorSpace;renderer.toneMapping=THREE.NoToneMapping;document.getElementById('view').appendChild(renderer.domElement);
 scene=new THREE.Scene();camera=new THREE.PerspectiveCamera(90,1,.02,100);controls=new OrbitControls(camera,renderer.domElement);controls.enableDamping=false;controls.addEventListener('change',()=>{if(spark&&!busy)drawStable().catch(error=>report(error.message));});
 const select=document.getElementById('pose');metadata.presets.forEach((p,i)=>select.add(new Option(p.label,i)));select.onchange=()=>matchedPose(+select.value).catch(error=>report(error.message));const initial=kind.startsWith('bath')&&!nearby?5:0;select.value=String(initial);await matchedPose(initial);
 const {SparkRenderer,SplatMesh}=await import('./vendor/spark/dist/spark.module.js');
 spark=new SparkRenderer({renderer,autoUpdate:false,onDirty:requestFrame,minSortIntervalMs:0,sortRadial:false,enableLod:false,preBlurAmount:0,blurAmount:.3});scene.add(spark);
 const url=kind==='fullNative'?'/checkpoints/explicit-full-final.ply':kind==='fullSog'?'/clean-final.sog':kind==='explicit20'?'/checkpoints/explicit-full-step20000.ply':kind==='explicit5'?'/checkpoints/explicit-full-step5000.ply':kind==='preview'?'/checkpoints/step-5000.ply':kind==='preview15'?'/checkpoints/step-15000.ply':kind==='preview30'?'/checkpoints/step-30000.ply':kind==='visibility30'?'/checkpoints/step-30000-visibility-preview.ply':kind==='bathDepth'?'/checkpoints/explicit-bath-depth.ply':kind==='bathSog'?'/explicit-bath-depth.sog':kind==='sog'?'/clean-final.sog':'/checkpoints/clean-final.ply';
 const fileType=(kind==='sog'||kind==='bathSog'||kind==='fullSog')?nativeSparkFileType('sog'):undefined;
 model=new SplatMesh({url,fileType,lod:false,editable:false,raycastable:false,extSplats:true,onProgress:event=>report(`Loading ${kind}: ${(event.loaded/1e6).toFixed(1)} MB${event.total?` / ${(event.total/1e6).toFixed(1)} MB`:''}`)});scene.add(model);await model.initialized;await renderer.compileAsync(scene,camera);await matchedPose(initial);
 evidence.kind=kind;evidence.loadSeconds=(performance.now()-started)/1000;evidence.splats=model.numSplats;evidence.renderer='Spark 2.4 / Three 0.180; all source splats, LoD disabled';evidence.mip={preBlurAmount:0,blurAmount:.3};
 document.getElementById('caption').textContent=kind==='fullNative'?'Full explicit pinhole/depth rebuild · final original Gaussian':kind==='fullSog'?'Full explicit pinhole/depth rebuild · same Gaussian / SOG':kind==='explicit20'?'Full explicit pinhole/depth rebuild · intermediate 20,000 steps':kind==='explicit5'?'Full explicit pinhole/depth rebuild · intermediate 5,000 steps':kind==='preview'?'Intermediate 5,000-step Gaussian':kind==='preview15'?'Intermediate 15,000-step Gaussian':kind==='preview30'?'Intermediate 30,000-step Gaussian':kind==='visibility30'?'Experimental visibility copy · not approved':kind==='bathDepth'?'Explicit pinhole/depth pilot · bathroom region only':kind==='bathSog'?'Same bathroom pilot · SOG transport compression':kind==='sog'?'Final Gaussian · SOG transport compression':'Rejected normals-only run · original Gaussian';
 select.disabled=false;document.getElementById('reset').disabled=false;document.getElementById('reset').onclick=()=>matchedPose(poseIndex);document.getElementById('save').onclick=()=>{const link=document.createElement('a');link.href=renderer.domElement.toDataURL('image/png');link.download=`clean-${kind}${nearby?'-nearby':''}${spark.sortRadial?'-radial':''}${document.getElementById('colour-direction').checked?'':'-sh0'}-pose-${poseIndex+1}.png`;link.click();};
 const radial=document.getElementById('radial'),directional=document.getElementById('colour-direction');radial.disabled=false;directional.disabled=false;
 radial.onchange=async()=>{spark.sortRadial=radial.checked;model.needsUpdate=true;await matchedPose(poseIndex);};
 directional.onchange=async()=>{model.splats.setMaxSh(directional.checked?2:0);model.needsUpdate=true;await matchedPose(poseIndex);};
}
