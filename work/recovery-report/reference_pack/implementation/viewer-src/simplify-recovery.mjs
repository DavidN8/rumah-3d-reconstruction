// UV/normal-aware simplification. Native meshes remain immutable.
import {MeshoptSimplifier as S} from 'meshoptimizer';
import {readFile,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
await S.ready;
const [input,output,targetArg='1900000',errorArg='0.002',protectFile,weightsArg]=process.argv.slice(2);
const weights=weightsArg?JSON.parse(weightsArg):[.01,.01,.01,.05,.05];
if(weights.length!==5||weights.some(x=>!Number.isFinite(x)||x<0))throw Error('Five nonnegative attribute weights are required');
if(!input||!output||input===output)throw Error('Distinct input and output paths are required');
const raw=await readFile(input),jn=raw.readUInt32LE(12),doc=JSON.parse(raw.subarray(20,20+jn).toString()),base=28+jn;
const oldDoc=structuredClone(doc),oldBin=raw.subarray(base);const chunks=[];let length=0;doc.accessors=[];doc.bufferViews=[];
function blob(bytes,target){const pad=(4-length%4)%4;if(pad){chunks.push(Buffer.alloc(pad));length+=pad;}const i=doc.bufferViews.length;doc.bufferViews.push({buffer:0,byteOffset:length,byteLength:bytes.length,...(target?{target}:{})});chunks.push(bytes);length+=bytes.length;return i;}
function get(ai){const a=oldDoc.accessors[ai],v=oldDoc.bufferViews[a.bufferView],n={SCALAR:1,VEC2:2,VEC3:3,VEC4:4}[a.type],size={5126:4,5125:4,5123:2,5121:1}[a.componentType];if(!n||!size)throw Error('Unsupported accessor');const C={5126:Float32Array,5125:Uint32Array,5123:Uint16Array,5121:Uint8Array}[a.componentType],out=new C(a.count*n),off=(v.byteOffset||0)+(a.byteOffset||0),stride=v.byteStride||size*n;
 for(let i=0;i<a.count;i++)for(let k=0;k<n;k++){const at=off+i*stride+k*size;out[i*n+k]=a.componentType===5126?oldBin.readFloatLE(at):a.componentType===5125?oldBin.readUInt32LE(at):a.componentType===5123?oldBin.readUInt16LE(at):oldBin[at];}return out;}
function put(arr,type,ct){const vi=blob(Buffer.from(arr.buffer,arr.byteOffset,arr.byteLength),type==='SCALAR'?34963:34962),rec={bufferView:vi,componentType:ct,count:arr.length/{SCALAR:1,VEC2:2,VEC3:3,VEC4:4}[type],type};if(type==='VEC3'){const lo=[Infinity,Infinity,Infinity],hi=[-Infinity,-Infinity,-Infinity];for(let i=0;i<arr.length;i++){const k=i%3;lo[k]=Math.min(lo[k],arr[i]);hi[k]=Math.max(hi[k],arr[i]);}rec.min=lo;rec.max=hi;}doc.accessors.push(rec);return doc.accessors.length-1;}
let original=0;for(const m of oldDoc.meshes)for(const p of m.primitives)original+=oldDoc.accessors[p.indices].count/3;
const target=Number(targetArg),reports=[];
const protection=protectFile?JSON.parse(await readFile(protectFile,'utf8')):{};
for(let mi=0;mi<doc.meshes.length;mi++)for(let pi=0;pi<doc.meshes[mi].primitives.length;pi++){
 const meshName=doc.meshes[mi].name||'mesh-'+mi;const p=doc.meshes[mi].primitives[pi],op=oldDoc.meshes[mi].primitives[pi],pos=get(op.attributes.POSITION),normal=get(op.attributes.NORMAL),uv=get(op.attributes.TEXCOORD_0),idx=new Uint32Array(get(op.indices));
 const attrs=new Float32Array(pos.length/3*5);for(let i=0;i<pos.length/3;i++){attrs.set(normal.subarray(i*3,i*3+3),i*5);attrs.set(uv.subarray(i*2,i*2+2),i*5+3);}
 const wanted=Math.max(3,Math.floor(idx.length*target/original/3)*3),flags=['LockBorder','ErrorAbsolute'];
 const protectionEntry=protection[meshName],protectedPoints=Array.isArray(protectionEntry)?protectionEntry:(protectionEntry?.points||[]),protectedBoxes=protectionEntry?.boxes||[];
 const vertexLock=protectionEntry?new Uint8Array(pos.length/3):null;
 if(vertexLock)for(let i=0;i<vertexLock.length;i++){
  for(const b of protectedBoxes)if(pos[i*3]>=b[0][0]&&pos[i*3]<=b[1][0]&&pos[i*3+1]>=b[0][1]&&pos[i*3+1]<=b[1][1]&&pos[i*3+2]>=b[0][2]&&pos[i*3+2]<=b[1][2]){vertexLock[i]=1;break;}
  if(!vertexLock[i])for(const p of protectedPoints){const x=pos[i*3]-p[0],y=pos[i*3+1]-p[1],z=pos[i*3+2]-p[2];if(x*x+y*y+z*z<.0004){vertexLock[i]=1;break;}}
 }
 const [indices,error]=S.simplifyWithAttributes(idx,pos,3,attrs,5,weights,vertexLock,wanted,Number(errorArg),flags);
 // No Prune, Sloppy, Permissive, border unlock or vertex movement. The
 // returned estimate is not an independently measured Hausdorff guarantee.
 if(error>Number(errorArg)+.000001)throw Error('Simplifier exceeded configured error estimate');
 const remap=new Int32Array(pos.length/3);remap.fill(-1);let count=0;for(const i of indices)if(remap[i]<0)remap[i]=count++;
 const newIdx=new Uint32Array(indices.length);for(let i=0;i<indices.length;i++)newIdx[i]=remap[indices[i]];
 p.attributes={};for(const [key,ai]of Object.entries(op.attributes)){const a=oldDoc.accessors[ai],src=get(ai),n={VEC2:2,VEC3:3,VEC4:4}[a.type],dest=new Float32Array(count*n);for(let i=0;i<remap.length;i++)if(remap[i]>=0)dest.set(src.subarray(i*n,i*n+n),remap[i]*n);p.attributes[key]=put(dest,a.type,5126);}
 p.indices=put(newIdx,'SCALAR',5125);reports.push({mesh:meshName,sourceTriangles:idx.length/3,triangles:indices.length/3,requestedTriangles:wanted/3,estimatedAbsoluteError:error,attributeWeights:weights,protectedVertices:vertexLock?vertexLock.reduce((s,x)=>s+x,0):0,flags,positionsNormalsUvsUnchangedForRetainedVertices:true});
}
const tex=[];for(let i=0;i<doc.images.length;i++){const image=oldDoc.images[i],v=oldDoc.bufferViews[image.bufferView],bytes=oldBin.subarray(v.byteOffset||0,(v.byteOffset||0)+v.byteLength);doc.images[i]={...image,bufferView:blob(bytes)};tex.push(createHash('sha256').update(bytes).digest('hex'));}
doc.extras={...(doc.extras||{}),simplification:{library:'meshoptimizer 0.25.0',errorLimitApproximateMetres:Number(errorArg),locksBorders:true,preservesUvSeams:true,prunesComponents:false,independentDeviationMeasurement:false}};
const pad=(4-length%4)%4;if(pad){chunks.push(Buffer.alloc(pad));length+=pad;}doc.buffers=[{byteLength:length}];let json=Buffer.from(JSON.stringify(doc));json=Buffer.concat([json,Buffer.alloc((4-json.length%4)%4,32)]);const header=Buffer.alloc(20);header.writeUInt32LE(0x46546c67,0);header.writeUInt32LE(2,4);header.writeUInt32LE(28+json.length+length,8);header.writeUInt32LE(json.length,12);header.writeUInt32LE(0x4e4f534a,16);const bh=Buffer.alloc(8);bh.writeUInt32LE(length);bh.writeUInt32LE(0x004e4942,4);
await writeFile(output,Buffer.concat([header,json,bh,...chunks]));const report={input,output,originalTriangles:original,triangles:reports.reduce((s,r)=>s+r.triangles,0),bytes:28+json.length+length,primitives:reports,textureSha256:tex,sourceSurfacesDeletedByOwnershipFilter:0,requiresMatchedCameraHoleRegressionGate:true};await writeFile(output+'.json',JSON.stringify(report,null,2));console.log(JSON.stringify(report,null,2));
