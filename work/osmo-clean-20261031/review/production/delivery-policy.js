// MB download limits are decimal; decoded geometry memory is measured in MiB.
export const OSMO_LIMITS=Object.freeze({fileBytes:50000000,textureSize:4096,
  preferredGeometryBytes:128*1024*1024,maximumGeometryBytes:192*1024*1024,
  simplificationWorldError:.003});

export function compressionTarget({triangles,bytes,decodedGeometryBytes}){
  if(![triangles,bytes,decodedGeometryBytes].every(Number.isFinite)||triangles<1||bytes<1||decodedGeometryBytes<1)
    throw Error('Cannot estimate a simplification target from invalid compression costs.');
  if(bytes<=OSMO_LIMITS.fileBytes&&decodedGeometryBytes<=OSMO_LIMITS.maximumGeometryBytes)return null;
  const ratio=Math.min(OSMO_LIMITS.fileBytes/bytes,OSMO_LIMITS.maximumGeometryBytes/decodedGeometryBytes);
  return Math.max(1,Math.min(triangles-1,Math.floor(triangles*ratio*.94)));
}
