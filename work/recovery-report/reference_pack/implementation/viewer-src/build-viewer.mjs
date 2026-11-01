import {build} from 'esbuild';
import {readFile,writeFile,open,rename,stat} from 'node:fs/promises';
import {fileURLToPath,pathToFileURL} from 'node:url';
const root=new URL('../',import.meta.url),review=process.env.ROOM_REVIEW_DIR?pathToFileURL(process.env.ROOM_REVIEW_DIR.replace(/[\\/]?$/,'/')):new URL('review/',root);
await build({entryPoints:[fileURLToPath(new URL('room-viewer.js',import.meta.url))],outfile:fileURLToPath(new URL('room-viewer.bundle.js',review)),bundle:true,minify:true,format:'iife',target:'es2022',logLevel:'info'});
const shell=await readFile(new URL('room-shell.html',import.meta.url),'utf8');
const normal=shell.replace('<!--EMBED-->','').replace('<!--SCRIPT-->','<script src="room-viewer.bundle.js"></script>');
await writeFile(new URL('index.html',review),normal);
await writeFile(new URL('mesh-viewer.html',review),normal);
if(process.env.ROOM_BUILD_STANDALONE==='0'){console.log('Staged HTTP viewer built.');process.exit(0);}
const cameras=JSON.parse(await readFile(new URL('cameras.json',review),'utf8'));
const sources={};
for(const c of cameras.presets)sources[c.name]='data:image/jpeg;base64,'+(await readFile(new URL(c.source,review))).toString('base64');
const modelBytes=await readFile(new URL('models/iphone-full-room.glb',review));
const embed={cameras,sources,modelByteLength:modelBytes.length,modelChunks:[]};
const js=(await readFile(new URL('room-viewer.bundle.js',review),'utf8')).replace(/<\/script/gi,'<\\/script');
// Stream bounded chunks: one 435MB GLB would exceed V8's single base64-string
// limit. Each chunk decodes independently into its exact offset in one buffer.
const parts=shell.split('<!--EMBED-->');if(parts.length!==2)throw Error('Expected one embedding marker');
const temporary=new URL('iPhone-Full-Room-preview.writing.html',review),final=new URL('iPhone-Full-Room-preview.html',review),handle=await open(temporary,'w');
let chunks=0;
try{
 await handle.writeFile(parts[0]+'<script>window.ROOM_EMBED='+JSON.stringify(embed).replace(/</g,'\\u003c')+';</script>');
 const chunkSize=24*1024*1024;
 for(let offset=0;offset<modelBytes.length;offset+=chunkSize){
  const encoded=modelBytes.subarray(offset,Math.min(offset+chunkSize,modelBytes.length)).toString('base64');
  await handle.writeFile('<script>window.ROOM_EMBED.modelChunks.push("'+encoded+'");document.currentScript.remove();</script>');chunks++;
 }
 await handle.writeFile(parts[1].replace('<!--SCRIPT-->',()=>'<script>'+js+'</script>'));
}finally{await handle.close();}
await rename(temporary,final);
console.log('HTTP viewer and standalone HTML built; standalone MB',(await stat(final)).size/1e6,'model chunks',chunks);
