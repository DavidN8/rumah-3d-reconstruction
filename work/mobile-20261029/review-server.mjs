import http from 'node:http';
import {readFile,stat,writeFile} from 'node:fs/promises';
import {createReadStream} from 'node:fs';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
const root=fileURLToPath(new URL('public/',import.meta.url));
const build=JSON.parse(await readFile(new URL('build-report.json',import.meta.url),'utf8'));
const phone=JSON.parse(await readFile(new URL('phone-asset-report.json',import.meta.url),'utf8'));
const mime={'.html':'text/html; charset=utf-8','.js':'text/javascript; charset=utf-8','.json':'application/json','.jpg':'image/jpeg','.glb':'model/gltf-binary','.txt':'text/plain'};
const server=http.createServer(async(req,res)=>{try{
  const url=new URL(req.url,'http://127.0.0.1'),route=decodeURIComponent(url.pathname);
  const qa=new URL(req.headers.referer||'http://127.0.0.1').searchParams.get('qa');
  if(route==='/'+build.manifestName&&['missing','truncated','stall'].includes(qa)){
    const m=JSON.parse(await readFile(path.join(root,build.manifestName),'utf8'));m.models.phone.url=`/qa/${qa}.glb`;
    res.writeHead(200,{'content-type':'application/json','cache-control':'no-store'});res.end(JSON.stringify(m));return;
  }
  if(route==='/qa/missing.glb'){res.writeHead(404,{'content-type':'text/plain'});res.end('No model');return;}
  if(route==='/qa/truncated.glb'||route==='/qa/stall.glb'){
    const bytes=(await readFile(path.join(root,phone.phoneFile))).subarray(0,16384);
    res.writeHead(200,{'content-type':'model/gltf-binary','cache-control':'no-store'});res.write(bytes);
    if(route.includes('truncated'))res.end();else req.on('close',()=>res.destroy());return;
  }
  const file=path.resolve(root,'.'+(route==='/'?'/index.html':route));
  if(!file.startsWith(path.resolve(root)+path.sep)){res.writeHead(403);res.end();return;}
  let selected=file,compressed=false;
  if(/gzip/.test(req.headers['accept-encoding']||'')&&file.endsWith('.glb')&&!req.headers.range){try{await stat(file+'.gz');selected=file+'.gz';compressed=true;}catch{}}
  const info=await stat(selected);if(!info.isFile())throw Error('Not a file');
  const headers={'content-type':mime[path.extname(file)]||'application/octet-stream','cache-control':'no-store','content-length':info.size,...(compressed?{'content-encoding':'gzip','vary':'Accept-Encoding'}:{})};
  res.writeHead(200,headers);if(req.method==='HEAD'){res.end();return;}createReadStream(selected).pipe(res);
}catch(error){res.writeHead(404,{'content-type':'text/plain'});res.end('Not found');}});
server.listen(0,'127.0.0.1',async()=>{const port=server.address().port;await writeFile(new URL('review-server.json',import.meta.url),JSON.stringify({pid:process.pid,port,url:`http://127.0.0.1:${port}/`}));console.log(`Rumah mobile review: http://127.0.0.1:${port}/`);});
