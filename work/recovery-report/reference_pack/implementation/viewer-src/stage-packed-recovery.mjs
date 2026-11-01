import {readFile,writeFile,mkdir,copyFile,cp,stat} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
const [sourceStage,destinationStage,model]=process.argv.slice(2),root=fileURLToPath(new URL('../recovery-v2/review/',import.meta.url));
for(const s of [sourceStage,destinationStage])if(!s||!/^[-a-zA-Z0-9]+$/.test(s))throw Error('Invalid review stage');
const src=path.join(root,sourceStage),dst=path.join(root,destinationStage),meta=JSON.parse(await readFile(path.join(src,'cameras.json'),'utf8'));
await mkdir(path.join(dst,'models'),{recursive:true});await copyFile(model,path.join(dst,'models','iphone-full-room.glb'));await cp(path.join(src,'sources'),path.join(dst,'sources'),{recursive:true});
meta.fileBytes=(await stat(model)).size;meta.title='iPhone rebuild review';meta.qualityMessage='Rebuild preview · visible defects remain · approximate scale';meta.losslessBufferCompression=true;
await writeFile(path.join(dst,'cameras.json'),JSON.stringify(meta));console.log(dst);
