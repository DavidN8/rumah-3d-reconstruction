"""Apply narrowly scoped native-viewer changes to the isolated production copy only."""
from pathlib import Path
HERE=Path(__file__).resolve().parent/'production'
def edit(name,old,new):
    file=HERE/name;text=file.read_text(encoding='utf-8');assert old in text,(name,old[:100]);file.write_text(text.replace(old,new),encoding='utf-8')
edit('loader-core.js',"import {OSMO_LIMITS} from './delivery-policy.js';", "import {OSMO_LIMITS} from './delivery-policy.js';\nimport {nativePolicy,validateModelHeader} from './native-delivery.js';")
edit('loader-core.js',"if(!Number.isSafeInteger(asset.maxTextureSize)","if(asset.representation==='gaussian')nativePolicy(asset);\n  if(asset.representation!=='gaussian'&&(!Number.isSafeInteger(asset.maxTextureSize)")
edit('loader-core.js',"asset.maxTextureSize>textureLimit)","asset.maxTextureSize>textureLimit))")
edit('loader-core.js',"{signal,onProgress=()=>{}}={}","{signal,onProgress=()=>{},format='glb'}={}")
edit('loader-core.js',"const header=new DataView(result.buffer);\n  if(header.getUint32(0,true)!==0x46546c67||header.getUint32(4,true)!==2||header.getUint32(8,true)!==expectedBytes)","if(!validateModelHeader(result,format))")
edit('chooser.js',"script.defer=true;","script.defer=true;script.type='module';")
edit('room-viewer.js',"import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js';\nimport {MeshoptDecoder} from 'meshoptimizer';", "import {nativePolicy} from './native-delivery.js';")
edit('room-viewer.js',"let renderer,rendererError;","let renderer,rendererError,spark;\nlet nativeGaussian=false;")
edit('room-viewer.js',"antialias:!phoneInput","antialias:selectedOnOpen==='osmo'?false:!phoneInput")
edit('room-viewer.js',"if(!model)return;\n  model.traverse", "if(!model)return;\n  if(nativeGaussian){seeInside=false;$('see-inside').setAttribute('aria-pressed','false');invalidate();return;}\n  model.traverse")
edit('room-viewer.js',"function controlsEnabled(value){for(const button of document.querySelectorAll('[data-3d],[data-move]'))button.disabled=!value;}","function controlsEnabled(value){for(const button of document.querySelectorAll('[data-3d],[data-move]'))button.disabled=!value;for(const id of ['shade','see-inside']){$(id).hidden=nativeGaussian;if(nativeGaussian)$(id).disabled=true;}}")
edit('room-viewer.js',"triangles:modelDiagnostics.triangles||0,geometryMiB:","representation:nativeGaussian?'gaussian':'mesh',splats:modelDiagnostics.splats||0,lodSplatBudget:modelDiagnostics.lodSplatBudget||0,triangles:modelDiagnostics.triangles||0,geometryMiB:")
edit('room-viewer.js',"function disposeModel(root){\n  if(!root)return;", "function disposeModel(root){\n  if(root?.isSplatMesh||root?.userData?.nativeGaussian){scene.remove(root);root.dispose();if(spark){scene.remove(spark);spark.dispose();spark=null;}renderer?.renderLists.dispose();return;}\n  if(!root)return;")
edit('room-viewer.js',"selection=selectModel(manifest,quality);asset=selection.asset;data=selection.cameraData;","selection=selectModel(manifest,quality);asset=selection.asset;data=selection.cameraData;nativeGaussian=asset.representation==='gaussian';")
edit('room-viewer.js',"buffer=await readModel(response,asset.fileBytes,{signal:controller.signal,onProgress:","buffer=await readModel(response,asset.fileBytes,{signal:controller.signal,format:asset.format||'glb',onProgress:")
old="""    const loader=new GLTFLoader().setMeshoptDecoder(MeshoptDecoder);
    let abandoned=false;
    const parsing=loader.parseAsync(buffer,'').then(gltf=>{if(abandoned||!loads.current(generation)){disposeModel(gltf.scene);throw new DOMException('Superseded','AbortError');}return gltf;});
    let gltf;
    try{gltf=await withDeadline(parsing,selection.prepareTimeout,'The browser could not prepare this 3D view. Retry a lightweight view or use Photos.');}
    catch(error){abandoned=true;throw error;}
    buffer=null;
    if(!loads.current(generation)){disposeModel(gltf.scene);return;}
    model=gltf.scene;scene.add(model);modelDiagnostics=inspectModel(model);
    if(selection.lite&&(modelDiagnostics.geometryMiB>selection.geometryLimit||modelDiagnostics.textures.some(([w,h])=>w>selection.textureLimit||h>selection.textureLimit)))throw Error('The lightweight view exceeded its graphics budget. Please use Photos and report this message.');
    ready=true;home();if(selection.lite||params.get('mode')==='orbit')setMode('orbit');resize();"""
new="""    if(nativeGaussian){
      const policy=nativePolicy(asset,phoneInput);
      setPhase('preparing','Preparing the 3D room…','The download is complete. Preparing the view for this device.');
      const {SparkRenderer,SplatMesh}=await import('../vendor/spark/dist/spark.module.js');
      spark=new SparkRenderer({renderer,onDirty:invalidate,lodSplatCount:policy.lodSplatCount,sortRadial:true,preBlurAmount:0,blurAmount:.3,minSortIntervalMs:phoneInput?24:12});scene.add(spark);
      const candidate=new SplatMesh({fileBytes:buffer,fileType:asset.format,fileName:asset.url,lod:true,nonLod:false,extSplats:false,editable:false,raycastable:false});candidate.userData.nativeGaussian=true;
      // Free the reference to the downloaded bytes as soon as the worker takes them.
      buffer=null;
      let abandoned=false;
      const parsing=candidate.initialized.then(result=>{if(abandoned||!loads.current(generation)){candidate.dispose();throw new DOMException('Superseded','AbortError');}return result;});
      try{model=await withDeadline(parsing,selection.prepareTimeout,'The browser could not prepare this room. Choose a model to retry, or use Photos.');}
      catch(error){abandoned=true;candidate.dispose();scene.remove(spark);spark.dispose();spark=null;throw error;}
      if(!loads.current(generation)){disposeModel(model);return;}scene.add(model);
      if(asset.worldFromTraining){model.matrix.fromArray(asset.worldFromTraining);model.matrixAutoUpdate=false;}
      const [lo,hi]=data.bounds,points=[];for(const x of [lo[0],hi[0]])for(const y of [lo[1],hi[1]])for(const z of [lo[2],hi[2]])points.push(x,y,z);framingPoints=Float32Array.from(points);
      modelDiagnostics={splats:asset.splats,lodSplatBudget:policy.lodSplatCount,triangles:0,geometryMiB:0,textures:[]};
    }else{
      const [{GLTFLoader},{MeshoptDecoder}]=await Promise.all([import('three/addons/loaders/GLTFLoader.js'),import('meshoptimizer')]);
      const loader=new GLTFLoader().setMeshoptDecoder(MeshoptDecoder);
      let abandoned=false;
      const parsing=loader.parseAsync(buffer,'').then(gltf=>{if(abandoned||!loads.current(generation)){disposeModel(gltf.scene);throw new DOMException('Superseded','AbortError');}return gltf;});
      let gltf;
      try{gltf=await withDeadline(parsing,selection.prepareTimeout,'The browser could not prepare this 3D view. Retry a lightweight view or use Photos.');}
      catch(error){abandoned=true;throw error;}
      buffer=null;
      if(!loads.current(generation)){disposeModel(gltf.scene);return;}
      model=gltf.scene;scene.add(model);modelDiagnostics=inspectModel(model);
      if(selection.lite&&(modelDiagnostics.geometryMiB>selection.geometryLimit||modelDiagnostics.textures.some(([w,h])=>w>selection.textureLimit||h>selection.textureLimit)))throw Error('The lightweight view exceeded its graphics budget. Please use Photos and report this message.');
    }
    ready=true;home();if(!nativeGaussian&&(selection.lite||params.get('mode')==='orbit'))setMode('orbit');resize();"""
edit('room-viewer.js',old,new)
edit('room-viewer.js',"${(modelDiagnostics.triangles/1e6).toFixed(2)}M triangles", "${nativeGaussian?(modelDiagnostics.splats/1e6).toFixed(2)+'M splats':(modelDiagnostics.triangles/1e6).toFixed(2)+'M triangles'}")
edit('room-viewer.js',"window.addEventListener('pagehide',()=>{loads.cancel();release();});", "window.addEventListener('pagehide',()=>{loads.cancel();release();disposeModel(model);renderer?.dispose();});")
for name in ('room-viewer.js','chooser.js'):
    edit(name,'20261031-osmo-v3','20261031-native-provisional')
print('Prepared isolated native branch; original site files untouched.')
