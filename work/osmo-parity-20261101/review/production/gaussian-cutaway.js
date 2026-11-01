// Reversible, world-space shell visibility. The downloaded source is never edited.
// A height test alone cannot remove vertical walls, doors or furniture here.
export function installCutaway({dyno,THREE,model,shell}){
 if(!shell?.perimeterPlanes?.length)throw Error('Occupied shell metadata is required for the overview.');
 const enabled=dyno.dynoBool(false),view=dyno.dynoVec3(new THREE.Vector3());
 const ceiling=Number(shell.ceilingY-shell.ceilingBand).toFixed(6),floor=Number(shell.floorY+.12).toFixed(6);
 const gl=n=>Number(n).toFixed(7);
 const boundary=shell.perimeterPlanes.map(([nx,nz,d])=>`{
   vec2 normal=vec2(${gl(nx)},${gl(nz)});
   float distance=dot(normal,p.xz)-${gl(d)};
   if(abs(distance)<${gl(shell.perimeterBand)} && abs(dot(n.xz,normal))>0.85 &&
      dot(normal,${'VIEW'}.xz)-${gl(d)}>0.05 && p.y>${floor}) hidden=true;
 }`).join('\n');
 const [lo,hi]=shell.bounds;
 const observers=(shell.interiorCameras||[]).map(c=>`{ vec3 observer=vec3(${c.map(gl).join(',')});float d=dot(p-observer,p-observer);if(d<nearestDistance){nearestDistance=d;nearest=observer;} }`).join('\n');
 const modifier=dyno.dynoBlock({gsplat:dyno.Gsplat},{gsplat:dyno.Gsplat},({gsplat})=>{
  const normal=dyno.gsplatNormal(gsplat);
  const operation=new dyno.Dyno({inTypes:{gsplat:dyno.Gsplat,normal:'vec3',enabled:'bool',view:'vec3'},outTypes:{gsplat:dyno.Gsplat},inputs:{gsplat,normal,enabled,view},statements:({inputs:i,outputs:o})=>[
   `${o.gsplat}=${i.gsplat};`,
   `if(${i.enabled}){ vec3 p=${i.gsplat}.center; vec3 n=${i.normal}; bool hidden=false;
      // Gaussian covariance normals have no sign. Orient to the nearest actual
      // interior capture before applying the same back-face semantics as a mesh.
      float nearestDistance=1e20;vec3 nearest=p+vec3(0.0,1.0,0.0);${observers}
      if(dot(n,nearest-p)<0.0)n=-n;
      if(dot(n,${i.view}-p)<-0.015)hidden=true;
      // Ceiling cap: horizontal normal AND high ceiling band. Never a blanket height slice.
      if(p.y>${ceiling} && abs(n.y)>0.65) hidden=true;
      if(abs(n.y)<0.45){ ${boundary.replaceAll('VIEW',i.view)} }
      // Exclude remote sparse-ray floaters only in the overview.
      if(any(lessThan(p,vec3(${lo.map(v=>gl(v-.25)).join(',')}))) ||
         any(greaterThan(p,vec3(${hi.map(v=>gl(v+.25)).join(',')})))) hidden=true;
      if(hidden) ${o.gsplat}.rgba.a=0.0;
    }`
  ]});
  return operation.outputs;
 });
 model.worldModifiers=[modifier];model.updateGenerator();
 return {update(active,camera){const changed=enabled.value!==active||(active&&!view.value.equals(camera.position));enabled.value=active;view.value.copy(camera.position);if(changed)model.updateVersion();},method:'normal-gated ceiling + view-dependent perimeter planes; reversible opacity'};
}
