export const NATIVE_LIMITS=Object.freeze({fileBytes:50_000_000,baseSplats:3_100_000,phoneRenderedSplats:750_000,desktopRenderedSplats:2_000_000});
export function nativeSparkFileType(format){
 // Spark's API calls a zipped .sog file "pcsogszip". Passing the filename
 // extension as an explicit type bypasses auto-detection and cannot decode it.
 if(format==='sog')return 'pcsogszip';
 if(format==='spz')return 'spz';
 throw Error('Unsupported native room format.');
}
export function nativePolicy(asset,phone=false){
 if(asset.representation!=='gaussian'||!['spz','sog'].includes(asset.format))throw Error('Unsupported native room format.');
 if(!Number.isSafeInteger(asset.fileBytes)||asset.fileBytes<12||asset.fileBytes>NATIVE_LIMITS.fileBytes)throw Error('Native room exceeds its download budget.');
 if(!Number.isSafeInteger(asset.splats)||asset.splats<1||asset.splats>NATIVE_LIMITS.baseSplats)throw Error('Native room exceeds its decoded splat budget.');
 return {lodSplatCount:phone?NATIVE_LIMITS.phoneRenderedSplats:NATIVE_LIMITS.desktopRenderedSplats,baseSplats:asset.splats,lod:true,nonLod:false,extSplats:false};
}
export function validateModelHeader(bytes,format='glb'){
 const view=new DataView(bytes.buffer,bytes.byteOffset,bytes.byteLength);
 if(format==='glb')return view.getUint32(0,true)===0x46546c67&&view.getUint32(4,true)===2&&view.getUint32(8,true)===bytes.byteLength;
 if(format==='spz')return (bytes[0]===0x1f&&bytes[1]===0x8b)||view.getUint32(0,true)===0x5053474e;
 if(format==='sog')return view.getUint32(0,true)===0x04034b50;
 return false;
}

// Decoding the file is not sufficient: Spark's first sort may still be pending.
// Keep the loading state until an actual draw has a nonzero active splat count.
export async function waitForNativeDraw({update,draw,activeSplats,isCurrent=()=>true,signal,timeoutMs=30000}){
 let stopped=false,timer,rejectAbort;
 const abortError=()=>new DOMException('Room preparation cancelled','AbortError');
 const check=()=>{if(stopped||signal?.aborted||!isCurrent())throw abortError();};
 const aborted=new Promise((_,reject)=>{rejectAbort=reject;});
 const abort=()=>{stopped=true;rejectAbort(abortError());};
 signal?.addEventListener('abort',abort,{once:true});
 const work=(async()=>{
  for(;;){
   check();await update();check();draw();check();
   const count=activeSplats();
   if(Number.isFinite(count)&&count>0)return count;
   await new Promise(resolve=>setTimeout(resolve,16));
  }
 })();
 const deadline=new Promise((_,reject)=>{timer=setTimeout(()=>{
  stopped=true;reject(new Error('The browser could not draw the room. Choose a model to retry, or use Photos.'));
 },timeoutMs);});
 try{return await Promise.race([work,deadline,aborted]);}
 finally{stopped=true;clearTimeout(timer);signal?.removeEventListener('abort',abort);}
}
