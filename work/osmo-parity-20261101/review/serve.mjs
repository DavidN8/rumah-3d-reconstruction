import http from 'node:http';import fs from 'node:fs';import path from 'node:path';import {fileURLToPath} from 'node:url';
const here=path.dirname(fileURLToPath(import.meta.url)),work=path.resolve(here,'../..');
const mime={'.js':'text/javascript','.mjs':'text/javascript','.json':'application/json','.html':'text/html','.png':'image/png','.jpg':'image/jpeg','.wasm':'application/wasm'};
const roots=[['/baseline/',path.join(work,'osmo-clean-20261031/review/production/public')],['/three/',path.join(work,'mobile-20261029/node_modules/three')],['/review/',here],['/',path.join(here,'production/public')]];
http.createServer((req,res)=>{
 const pathname=decodeURIComponent(new URL(req.url,'http://localhost').pathname);if(pathname==='/favicon.ico'){res.writeHead(204).end();return;}const [prefix,root]=roots.find(([prefix])=>pathname.startsWith(prefix));
 const rel=pathname.slice(prefix.length)||'index.html',file=path.resolve(root,rel);
 if(!file.startsWith(path.resolve(root)+path.sep)){res.writeHead(403).end();return;}
 let stat;try{stat=fs.statSync(file);if(!stat.isFile())throw Error();}catch{res.writeHead(404).end('Missing');return;}
 res.setHeader('Cache-Control','no-store');res.setHeader('Content-Type',mime[path.extname(file)]||'application/octet-stream');res.setHeader('Content-Length',stat.size);
 if(req.method==='HEAD')res.end();else fs.createReadStream(file).pipe(res);
}).listen(53270,'127.0.0.1',()=>console.log('Isolated review http://127.0.0.1:53270/'));
