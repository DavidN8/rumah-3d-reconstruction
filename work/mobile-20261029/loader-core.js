export function chooseQuality({requested,coarse,touchPoints=0,width=1920,userAgent=''}) {
  if(requested==='phone'||requested==='native')return requested;
  return coarse||touchPoints>1||width<1000||/Android|iPhone|iPad|iPod/i.test(userAgent)?'phone':'native';
}

export async function readModel(response,expectedBytes,{signal,onProgress=()=>{}}={}) {
  if(!response.ok)throw new Error(`The 3D download failed (${response.status}). Please try again.`);
  const type=response.headers.get('content-type')||'';
  if(type.includes('text/html'))throw new Error('The server returned a web page instead of the 3D room. Please retry.');
  if(!Number.isSafeInteger(expectedBytes)||expectedBytes<12||expectedBytes>500*1024*1024)throw new Error('The 3D file size is invalid.');
  const result=new Uint8Array(expectedBytes);
  let received=0;
  const copy=chunk=>{
    if(signal?.aborted)throw new DOMException('Download cancelled','AbortError');
    if(received+chunk.length>expectedBytes)throw new Error('The 3D file size changed. Refresh this page and retry.');
    result.set(chunk,received);received+=chunk.length;onProgress(received,expectedBytes);
  };
  if(response.body?.getReader){
    const reader=response.body.getReader();
    try{for(;;){const item=await reader.read();if(item.done)break;copy(item.value);}}
    catch(error){await reader.cancel().catch(()=>{});throw error;}
    finally{reader.releaseLock();}
  }else copy(new Uint8Array(await response.arrayBuffer()));
  if(received!==expectedBytes)throw new Error('The download stopped before the whole room arrived. Please retry.');
  const header=new DataView(result.buffer);
  if(header.getUint32(0,true)!==0x46546c67||header.getUint32(4,true)!==2||header.getUint32(8,true)!==expectedBytes)
    throw new Error('The downloaded 3D file is incomplete. Please retry.');
  return result.buffer;
}

export function pinchRatio(previousDistance,nextDistance){
  if(!Number.isFinite(previousDistance)||!Number.isFinite(nextDistance)||previousDistance<2||nextDistance<2)return 1;
  return Math.max(.5,Math.min(2,previousDistance/nextDistance));
}

export async function withDeadline(task,milliseconds,message){
  let timer;
  try{return await Promise.race([task,new Promise((_,reject)=>{timer=setTimeout(()=>reject(new Error(message)),milliseconds);})]);}
  finally{clearTimeout(timer);}
}
