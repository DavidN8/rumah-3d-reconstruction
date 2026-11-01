import {build} from 'esbuild';
import {readFile,writeFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
const root=new URL('../',import.meta.url),review=new URL('review/',root);
await build({entryPoints:[fileURLToPath(new URL('room-viewer.js',import.meta.url))],outfile:fileURLToPath(new URL('room-viewer.bundle.js',review)),bundle:true,minify:true,format:'iife',target:'es2022',logLevel:'info'});
const shell=await readFile(new URL('room-shell.html',import.meta.url),'utf8');
const normal=shell.replace('<!--EMBED-->','').replace('<!--SCRIPT-->','<script src="room-viewer.bundle.js"></script>');
await writeFile(new URL('index.html',review),normal);
await writeFile(new URL('mesh-viewer.html',review),normal);
const cameras=JSON.parse(await readFile(new URL('cameras.json',review),'utf8'));
const sources={};
for(const c of cameras.presets)sources[c.name]='data:image/jpeg;base64,'+(await readFile(new URL(c.source,review))).toString('base64');
const embed={cameras,sources,model:(await readFile(new URL('models/iphone-full-room.glb',review))).toString('base64')};
const js=(await readFile(new URL('room-viewer.bundle.js',review),'utf8')).replace(/<\/script/gi,'<\\/script');
// Function replacements preserve literal $& / $' sequences inside bundled JS.
const standalone=shell.replace('<!--EMBED-->',()=>'<script>window.ROOM_EMBED='+JSON.stringify(embed).replace(/</g,'\\u003c')+';</script>').replace('<!--SCRIPT-->',()=>'<script>'+js+'</script>');
await writeFile(new URL('iPhone-Full-Room-preview.html',review),standalone);
console.log('HTTP viewer and standalone HTML built; standalone MB',Buffer.byteLength(standalone)/1e6);
