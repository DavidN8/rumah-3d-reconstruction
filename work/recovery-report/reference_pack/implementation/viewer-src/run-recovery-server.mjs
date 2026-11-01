import {spawn} from 'node:child_process';
import {writeFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
const root=new URL('../',import.meta.url),url='http://127.0.0.1:53254/recovery-v2/review/fast/';
try{const r=await fetch(url);if(r.ok){console.log('Existing recovery viewer at '+url);process.exit(0);}}catch{}
const child=spawn('C:/Python314/python.exe',['-m','http.server','53254','--bind','127.0.0.1','--directory',fileURLToPath(root)],{windowsHide:true,detached:true,stdio:'ignore'});child.unref();
await writeFile(new URL('recovery-v2/review/viewer-status.json',root),JSON.stringify({pid:child.pid,url,scope:'Recovery review candidates; production baseline unchanged'},null,2));console.log(url);
