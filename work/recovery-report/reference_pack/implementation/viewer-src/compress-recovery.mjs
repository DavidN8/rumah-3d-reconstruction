// Lossless buffer compression. Every decoded geometry byte and image is checked.
import {MeshoptEncoder as E,MeshoptDecoder as D} from 'meshoptimizer';
import {readFile,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
await Promise.all([E.ready,D.ready]);
const [input,output]=process.argv.slice(2);if(!input||!output||input===output)throw Error('Use distinct GLB paths');
const raw=await readFile(input),jn=raw.readUInt32LE(12),doc=JSON.parse(raw.subarray(20,20+jn)),bin=raw.subarray(28+jn),chunks=[],views=[],records=[];
let length=0,fallbackLength=0;
const hash=b=>createHash('sha256').update(b).digest('hex');
function append(bytes){const pad=(4-length%4)%4;if(pad){chunks.push(Buffer.alloc(pad));length+=pad;}const offset=length;chunks.push(Buffer.from(bytes));length+=bytes.length;return offset;}
for(let i=0;i<doc.bufferViews.length;i++){
 const v=doc.bufferViews[i],source=bin.subarray(v.byteOffset||0,(v.byteOffset||0)+v.byteLength),a=doc.accessors.find(a=>a.bufferView===i);
 if(a){
  if(a.byteOffset||v.byteStride)throw Error('Expected standalone, unstrided accessors');
  const size=source.length/a.count,mode=v.target===34963?'INDICES':'ATTRIBUTES';
  const encoded=E.encodeGltfBuffer(source,a.count,size,mode),decoded=new Uint8Array(source.length);D.decodeGltfBuffer(decoded,a.count,size,encoded,mode);
  if(!Buffer.from(decoded).equals(source))throw Error('Lossless round-trip failed for view '+i);
  const offset=append(encoded);views.push({...v,buffer:1,byteOffset:fallbackLength,extensions:{EXT_meshopt_compression:{buffer:0,byteOffset:offset,byteLength:encoded.length,byteStride:size,count:a.count,mode,filter:'NONE'}}});fallbackLength+=source.length;
  records.push({view:i,mode,sourceBytes:source.length,packedBytes:encoded.length,decodedSha256:hash(decoded),byteExact:true});
 }else{const offset=append(source);views.push({...v,buffer:0,byteOffset:offset});records.push({view:i,kind:'image',sourceBytes:source.length,sha256:hash(source),byteExact:true});}
}
const pad=(4-length%4)%4;if(pad){chunks.push(Buffer.alloc(pad));length+=pad;}
doc.bufferViews=views;doc.buffers=[{byteLength:length},{byteLength:fallbackLength,extensions:{EXT_meshopt_compression:{fallback:true}}}];
doc.extensionsUsed=[...new Set([...(doc.extensionsUsed||[]),'EXT_meshopt_compression'])];doc.extensionsRequired=[...new Set([...(doc.extensionsRequired||[]),'EXT_meshopt_compression'])];
doc.extras={...(doc.extras||{}),losslessCompression:'EXT_meshopt_compression; all decoded geometry bytes verified identical; no quantization'};
let json=Buffer.from(JSON.stringify(doc));json=Buffer.concat([json,Buffer.alloc((4-json.length%4)%4,32)]);const h=Buffer.alloc(20);h.writeUInt32LE(0x46546c67,0);h.writeUInt32LE(2,4);h.writeUInt32LE(28+json.length+length,8);h.writeUInt32LE(json.length,12);h.writeUInt32LE(0x4e4f534a,16);const bh=Buffer.alloc(8);bh.writeUInt32LE(length);bh.writeUInt32LE(0x004e4942,4);
const payload=Buffer.concat([h,json,bh,...chunks]);await writeFile(output,payload);const report={input,output,sourceSha256:hash(raw),packedSha256:hash(payload),sourceBytes:raw.length,packedBytes:28+json.length+length,allGeometryBytesRoundTripIdentical:true,textureBytesPreserved:true,quantization:false,records};await writeFile(output+'.compression.json',JSON.stringify(report,null,2));console.log(JSON.stringify({sourceBytes:raw.length,packedBytes:report.packedBytes,byteExact:true}));
