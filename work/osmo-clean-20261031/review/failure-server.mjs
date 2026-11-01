// Local transport-failure probe for the exact built viewer. No public changes.
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const here=path.dirname(fileURLToPath(import.meta.url));
const root=path.join(here,'production/public');
const log=fs.createWriteStream(path.join(here,'failure-requests.jsonl'),{flags:'a'});
const types={'.html':'text/html','.js':'text/javascript','.mjs':'text/javascript','.json':'application/json','.wasm':'application/wasm','.jpg':'image/jpeg','.png':'image/png'};
http.createServer((req,res)=>{
 const pathname=new URL(req.url,'http://127.0.0.1').pathname;
 const denied=pathname.startsWith('/models/');
 log.write(JSON.stringify({time:new Date().toISOString(),method:req.method,path:pathname,syntheticModelFailure:denied})+'\n');
 res.setHeader('Cache-Control','no-store');
 if(denied){res.writeHead(503,{'Content-Type':'text/plain','Content-Length':0});res.end();return;}
 const file=path.resolve(root,pathname==='/'?'index.html':pathname.slice(1));
 if(!file.startsWith(root+path.sep)){res.writeHead(403);res.end();return;}
 if(!fs.existsSync(file)||!fs.statSync(file).isFile()){res.writeHead(404);res.end();return;}
 res.writeHead(200,{'Content-Type':types[path.extname(file)]||'application/octet-stream','Content-Length':fs.statSync(file).size});
 if(req.method==='HEAD'){res.end();return;}
 fs.createReadStream(file).pipe(res);
}).listen(53268,'127.0.0.1',()=>console.log('Local deliberate model HTTP 503 probe: http://127.0.0.1:53268/'));
