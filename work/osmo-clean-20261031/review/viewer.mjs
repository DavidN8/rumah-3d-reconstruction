import * as THREE from 'three';
import {OrbitControls} from 'three/addons/controls/OrbitControls.js';
let renderer,camera,scene,controls,spark,model,metadata,kind,poseIndex=0,frame;
const status=document.getElementById('status');
export const evidence={};
function setStatus(s){status.textContent=s;}
export function matchedPose(index){
 poseIndex=index;const p=metadata.presets[index];camera.position.fromArray(p.position);camera.quaternion.fromArray(p.quaternion);camera.updateMatrixWorld(true);
 const [fx,fy,cx,cy]=p.intrinsics,W=p.imageWidth,H=p.imageHeight,n=.02,f=100;
 camera.projectionMatrix.makePerspective(-cx/fx*n,(W-cx)/fx*n,cy/fy*n,-(H-cy)/fy*n,n,f);camera.projectionMatrixInverse.copy(camera.projectionMatrix).invert();
 controls.target.copy(camera.position).add(new THREE.Vector3(0,0,-1).applyQuaternion(camera.quaternion));controls.update();
 document.getElementById('photo').src=`/reference/${index}.jpg`;evidence.pose={name:p.name,position:p.position,quaternion:p.quaternion,intrinsics:p.intrinsics,imageWidth:W,imageHeight:H};requestFrame();return evidence.pose;
}
function requestFrame(){if(frame)return;frame=requestAnimationFrame(()=>{frame=null;renderer.render(scene,camera);});}
export async function open(selected){
 kind=selected;const t=performance.now();metadata=await (await fetch('/cameras.json')).json();
 renderer=new THREE.WebGLRenderer({antialias:false,alpha:false,preserveDrawingBuffer:true,powerPreference:'high-performance'});renderer.setPixelRatio(1);renderer.setSize(600,600);renderer.setClearColor(0x000000);renderer.outputColorSpace=THREE.SRGBColorSpace;renderer.toneMapping=THREE.NoToneMapping;document.getElementById('view').appendChild(renderer.domElement);
 scene=new THREE.Scene();camera=new THREE.PerspectiveCamera(90,1,.02,100);controls=new OrbitControls(camera,renderer.domElement);controls.enableDamping=false;controls.addEventListener('change',requestFrame);
 const select=document.getElementById('pose');metadata.presets.forEach((p,i)=>select.add(new Option(p.label,i)));select.disabled=false;select.onchange=()=>matchedPose(+select.value);matchedPose(0);
 const progress=e=>setStatus(`Loading ${kind}: ${(e.loaded/1e6).toFixed(1)} MB${e.total?` / ${(e.total/1e6).toFixed(1)} MB`:''}`);
 if(kind==='mesh'){
  const [{GLTFLoader},{MeshoptDecoder}]=await Promise.all([import('three/addons/loaders/GLTFLoader.js'),import('/three/examples/jsm/libs/meshopt_decoder.module.js')]);
  const loader=new GLTFLoader();loader.setMeshoptDecoder(MeshoptDecoder);const result=await loader.loadAsync('/model/current.glb',progress);model=result.scene;
  model.traverse(o=>{if(o.isMesh){const old=o.material;o.material=new THREE.MeshBasicMaterial({map:old.map,side:THREE.DoubleSide,color:old.color});old.dispose();}});scene.add(model);
 }else{
  const {SparkRenderer,SplatMesh}=await import('./vendor/spark/dist/spark.module.js');
  // Exact-pose baseline keeps all 2,997,515 splats and disables LoD, matching mip antialiasing.
  spark=new SparkRenderer({renderer,sortRadial:false,enableLod:false,preBlurAmount:0,blurAmount:.3,onDirty:requestFrame});scene.add(spark);
  model=new SplatMesh({url:kind==='sog'?'/native-v4.sog':kind==='compressed'?'/model/native-v4.spz':'/model/native-v4.ply',lod:false,editable:false,raycastable:false,extSplats:true,onProgress:progress});scene.add(model);await model.initialized;
 }
 evidence.kind=kind;evidence.loadSeconds=(performance.now()-t)/1000;evidence.renderer=renderer.getContext().getParameter(renderer.getContext().VERSION);evidence.splatCount=model.numSplats??model.splats?.getNumSplats?.()??null;evidence.nativeRenderer='Spark 2.4.0 / Three 0.180.0, native Gaussian source; not Spirula reference backend';evidence.mip={preBlurAmount:0,blurAmount:.3};evidence.scope='Source poses and exact K. SPZ is transport-quantized; PLY remains baseline. Spark rendering may differ slightly from Spirula.';
 document.getElementById('caption').textContent=kind==='mesh'?'Published triangle mesh':kind==='sog'?'Actual Gaussian splats · compressed SOG':kind==='compressed'?'Actual Gaussian splats · compressed SPZ':'Actual Gaussian splats · original PLY';
 setStatus(`Loaded ${kind} in ${evidence.loadSeconds.toFixed(1)} s. ${evidence.splatCount?evidence.splatCount.toLocaleString()+' splats. ':''}Camera ${metadata.presets[poseIndex].name}`);
 document.getElementById('reset').disabled=false;document.getElementById('reset').onclick=()=>matchedPose(poseIndex);document.getElementById('save').disabled=false;document.getElementById('save').onclick=()=>{const a=document.createElement('a');a.href=renderer.domElement.toDataURL('image/png');a.download=`${kind}-pose-${poseIndex+1}.png`;a.click();};requestFrame();return evidence;
}
export async function screenshot(){renderer.render(scene,camera);return renderer.domElement.toDataURL('image/png');}
export function dispose(){if(frame)cancelAnimationFrame(frame);controls?.dispose();model?.dispose?.();spark?.dispose();renderer?.dispose();renderer?.forceContextLoss();}
