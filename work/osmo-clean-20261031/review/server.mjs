import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const here=path.dirname(fileURLToPath(import.meta.url));
const work=path.resolve(here,'../..');
const capture='C:/Users/bombe/OneDrive/Documents/ChatGPT/Ruang Kamare/roomscan-reconstruction/data/20261031_OSMO360';
const cameras=JSON.parse(fs.readFileSync(path.join(work,'mobile-20261029/legacy-osmo-cameras.json')));
const files=new Map([
 ['/model/native-v4.ply',capture+'/recovery-v2/training/osmo-surface-v4/step-000050000.ckpt/splat.ply'],
 ['/model/native-v4.spz',path.join(here,'native-v4.spz')],
 ['/model/current.glb',path.resolve(work,'../outputs/restored-legacy/osmo-lite-30ed8cb766.glb')],
]);
cameras.presets.forEach((pre,i)=>files.set(`/reference/${i}.jpg`,pre.sourceFile));
const mime={'.html':'text/html','.mjs':'text/javascript','.js':'text/javascript','.json':'application/json','.jpg':'image/jpeg','.png':'image/png','.wasm':'application/wasm','.glb':'model/gltf-binary','.ply':'application/octet-stream','.spz':'application/octet-stream'};
const log=fs.createWriteStream(path.join(here,'requests.jsonl'),{flags:'a'});
const server=http.createServer((req,res)=>{
 const pathname=new URL(req.url,'http://localhost').pathname;
 log.write(JSON.stringify({time:new Date().toISOString(),method:req.method,path:pathname})+'\n');
 res.setHeader('Cache-Control','no-store');
 if(pathname==='/cameras.json'){res.setHeader('Content-Type','application/json');res.end(JSON.stringify(cameras));return;}
 let file=files.get(pathname);
 if(!file){const root=pathname.startsWith('/three/')?path.join(work,'mobile-20261029/node_modules/three'):here;const rel=pathname.startsWith('/three/')?pathname.slice(7):pathname==='/'?'index.html':pathname.slice(1);file=path.resolve(root,rel);if(!file.startsWith(path.resolve(root)+path.sep)){res.writeHead(403);res.end();return;}}
 if(!fs.existsSync(file)||!fs.statSync(file).isFile()){res.writeHead(404);res.end('Not found');return;}
 const size=fs.statSync(file).size;res.setHeader('Content-Type',mime[path.extname(file)]||'application/octet-stream');
 const range=req.headers.range?.match(/^bytes=(\d+)-(\d*)$/);let start=0,end=size-1;
 if(range){start=+range[1];end=range[2]?Math.min(+range[2],size-1):size-1;if(start>end){res.writeHead(416);res.end();return;}res.writeHead(206,{'Content-Range':`bytes ${start}-${end}/${size}`,'Content-Length':end-start+1,'Accept-Ranges':'bytes'});}else{res.writeHead(200,{'Content-Length':size,'Accept-Ranges':'bytes'});}
 if(req.method==='HEAD'){res.end();return;}fs.createReadStream(file,{start,end}).pipe(res);
});
server.listen(53267,'127.0.0.1',()=>console.log('Offline-only review: http://127.0.0.1:53267'));
