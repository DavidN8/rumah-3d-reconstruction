// Simple-shape stand-in for the room (simple_shapes.py): boxes, cylinders and spheres,
// each a flat colour with a dark outline so the layout reads at a glance.
const TYPES=new Set(['box','cylinder','sphere']),KINDS=new Set(['floor','ceiling','wall','object']);
export const SHAPE_LIMIT=2000;
const finite=(v,n)=>Array.isArray(v)&&v.length===n&&v.every(Number.isFinite);
export function validateShapes(data){
 if(data?.version!==1||!Array.isArray(data.shapes)||!data.shapes.length||data.shapes.length>SHAPE_LIMIT)throw Error('Simple shapes are missing or malformed.');
 for(const s of data.shapes)if(!TYPES.has(s.type)||!KINDS.has(s.kind)||!finite(s.center,3)||!finite(s.size,3)||!s.size.every(v=>v>0&&v<50)||!Number.isFinite(s.yaw)||!/^#[0-9a-f]{6}$/.test(s.color)||(s.outward!==undefined&&!finite(s.outward,2)))throw Error('Simple shapes are missing or malformed.');
 return data;
}
// Overview cutaway for shapes: ceilings go, and exterior walls whose outside faces the camera.
export function shapeVisible(s,seeInside,camera){
 if(!seeInside)return true;if(s.kind==='ceiling')return false;
 return !s.outward||s.outward[0]*(camera.x-s.center[0])+s.outward[1]*(camera.z-s.center[2])<=0;
}
export function buildShapes(THREE,data){
 validateShapes(data);
 const unit={box:new THREE.BoxGeometry(1,1,1),cylinder:new THREE.CylinderGeometry(.5,.5,1,32),sphere:new THREE.SphereGeometry(.5,32,16)};
 const outline={box:new THREE.EdgesGeometry(unit.box),cylinder:new THREE.EdgesGeometry(unit.cylinder,30),sphere:null};
 const line=new THREE.LineBasicMaterial({color:0x1d2630,transparent:true,opacity:.5});
 const group=new THREE.Group();group.name='simple-shapes';
 for(const s of data.shapes){
  const mesh=new THREE.Mesh(unit[s.type],new THREE.MeshStandardMaterial({color:s.color,roughness:.85,metalness:0,flatShading:s.type==='box'}));
  mesh.position.fromArray(s.center);mesh.scale.fromArray(s.size);mesh.rotation.y=s.yaw;mesh.userData.shape=s;
  if(outline[s.type])mesh.add(new THREE.LineSegments(outline[s.type],line));
  group.add(mesh);
 }
 group.userData.dispose=()=>{for(const g of [...Object.values(unit),...Object.values(outline)])g?.dispose();line.dispose();group.traverse(o=>{if(o.isMesh)o.material.dispose();});};
 return group;
}
