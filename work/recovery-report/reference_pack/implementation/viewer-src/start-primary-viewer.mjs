import {spawn} from 'node:child_process';
import {fileURLToPath} from 'node:url';
const script=fileURLToPath(new URL('../review/serve.py',import.meta.url));
try{const r=await fetch('http://127.0.0.1:53251/viewer-status.json');if(r.ok&&(await r.json()).project==='20261027_IPHONE_WIDE'){console.log('Primary viewer already running');process.exit(0);}}catch{}
const child=spawn('C:/Python314/python.exe',[script],{windowsHide:true,detached:true,stdio:'ignore'});child.unref();console.log('Primary viewer at http://127.0.0.1:53251/');
