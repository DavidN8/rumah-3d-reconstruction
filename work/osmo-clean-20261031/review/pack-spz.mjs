// Isolated CPU-only transport experiment. No splat deletion, meshing, retraining or axis flip.
import fs from 'node:fs/promises';
import crypto from 'node:crypto';
import path from 'node:path';
import createSpzModule from './vendor/spz/dist/spz.js';

const args = process.argv.slice(2);
const smoke = args.includes('--smoke');
const source = args[args.indexOf('--source') + 1];
const output = args[args.indexOf('--output') + 1];
if (!smoke && (!args.includes('--source') || !args.includes('--output'))) throw Error('Use --smoke, or --source input.ply --output output.spz');
const spz = await createSpzModule();
let cloud;
if (smoke) {
  cloud = {numPoints: 1, shDegree: 0, antialiased: true, extensions: [], positions: new Float32Array([1,2,3]), scales: new Float32Array([-3,-4,-5]), rotations: new Float32Array([0,0,0,1]), alphas: new Float32Array([2]), colors: new Float32Array([0.1,0.2,0.3]), sh: new Float32Array()};
} else {
  const bytes = await fs.readFile(source);
  const end = bytes.indexOf('end_header\n') + 11;
  if (end < 11) throw Error('Missing PLY header');
  const header = bytes.subarray(0,end).toString('ascii');
  if (!header.includes('format binary_little_endian 1.0')) throw Error('Requires binary little-endian PLY');
  const properties = [...header.matchAll(/^property float (\S+)$/gm)].map(m=>m[1]);
  const required = ['x','y','z','nx','ny','nz','f_dc_0','f_dc_1','f_dc_2','opacity','scale_0','scale_1','scale_2','rot_0','rot_1','rot_2','rot_3'];
  if (JSON.stringify(properties)!==JSON.stringify(required)) throw Error('This audited converter accepts only the v4 SH0 schema; use a general official converter for SH1+');
  const n = +header.match(/element vertex (\d+)/)[1];
  if (bytes.byteLength !== end + n * 68) throw Error('Unexpected PLY payload length');
  cloud = {numPoints:n,shDegree:0,antialiased:true,extensions:[],positions:new Float32Array(n*3),scales:new Float32Array(n*3),rotations:new Float32Array(n*4),alphas:new Float32Array(n),colors:new Float32Array(n*3),sh:new Float32Array()};
  const view = new DataView(bytes.buffer,bytes.byteOffset+end,n*68);
  for(let i=0;i<n;i++) {
    const value=j=>view.getFloat32(i*68+j*4,true);
    for(let j=0;j<3;j++) {cloud.positions[i*3+j]=value(j);cloud.colors[i*3+j]=value(6+j);cloud.scales[i*3+j]=value(10+j);}
    cloud.alphas[i]=value(9);
    // PLY w,x,y,z -> SPZ x,y,z,w, no world coordinate conversion.
    for(let j=0;j<3;j++) cloud.rotations[i*4+j]=value(14+j);
    cloud.rotations[i*4+3]=value(13);
  }
}
const start=performance.now();
const packed=spz.saveSpzToBuffer(cloud,{version:3,from:spz.CoordinateSystem.RUB,sh1Bits:5,shRestBits:4});
if (!packed.length) throw Error('SPZ encoder returned an empty file');
const decoded=spz.loadSpzFromBuffer(packed,{to:spz.CoordinateSystem.RUB});
if(decoded.numPoints!==cloud.numPoints || decoded.shDegree!==0 || !decoded.antialiased) throw Error('Count/SH/antialias round-trip failed');
let maxPositionError=0,maxColorError=0,maxScaleLogError=0,maxOpacityError=0,maxRotationDegrees=0;
for(let i=0;i<cloud.numPoints;i++) {
  let dot=0,nn1=0,nn2=0;
  for(let j=0;j<3;j++) {const k=i*3+j;maxPositionError=Math.max(maxPositionError,Math.abs(decoded.positions[k]-cloud.positions[k]));maxColorError=Math.max(maxColorError,Math.abs(decoded.colors[k]-cloud.colors[k]));maxScaleLogError=Math.max(maxScaleLogError,Math.abs(decoded.scales[k]-cloud.scales[k]));}
  for(let j=0;j<4;j++) {const a=cloud.rotations[i*4+j],b=decoded.rotations[i*4+j];dot+=a*b;nn1+=a*a;nn2+=b*b;}
  maxRotationDegrees=Math.max(maxRotationDegrees,2*Math.acos(Math.min(1,Math.abs(dot/Math.sqrt(nn1*nn2))))*180/Math.PI);
  const sigmoid=x=>1/(1+Math.exp(-x));maxOpacityError=Math.max(maxOpacityError,Math.abs(sigmoid(decoded.alphas[i])-sigmoid(cloud.alphas[i])));
}
const report={source:smoke?'one synthetic splat':path.resolve(source),sourceBytes:smoke?null:(await fs.stat(source)).size,output:smoke?null:path.resolve(output),format:'SPZ v3, official Adobe/Niantic @adobe/spz 0.2.3',numPoints:cloud.numPoints,shDegree:0,antialiased:decoded.antialiased,packedBytes:packed.length,under50MB:packed.length<=50_000_000,sha256:crypto.createHash('sha256').update(packed).digest('hex'),axes:'Identity RUB / project Y-up; PLY wxyz quaternion reordered to SPZ xyzw',unchangedSplatCount:true,roundtrip:{maxPositionComponentErrorSceneUnits:maxPositionError,maxSH0ComponentError:maxColorError,maxScaleLogError,maxOpacityError,maxRotationDegrees},seconds:(performance.now()-start)/1000,limitation:'Compression is lossy. File budget is not a runtime memory budget. Visual quality and physical phone loading remain to be checked.'};
if(!smoke) {await fs.writeFile(output,packed);await fs.writeFile(output+'.json',JSON.stringify(report,null,2));}
console.log(JSON.stringify(report,null,2));
