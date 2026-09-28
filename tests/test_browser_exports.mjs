import fs from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {annotationFiles,makeZip,validateShapes} from '../dist/export-formats.mjs';
const base=new URL('../dist/',import.meta.url),manifest=JSON.parse(await fs.readFile(new URL('data/manifest.json',base),'utf8'));
const entries=new Map();
for(const row of manifest.files){const doc=JSON.parse(await fs.readFile(new URL('data/'+row.name+'.json',base),'utf8'));const image=new Uint8Array(await fs.readFile(new URL(doc.image,base)));for(const [key,value]of annotationFiles(doc,image))entries.set(key,value);}
const fixture=JSON.parse(await fs.readFile(new URL('data/1-125.json',base),'utf8'));fixture.name='edited-fixture';fixture.shapes[0].label='測□𠀀<&';fixture.shapes[0].box=[.2,.4,10.7,20.3];
const image=new Uint8Array(await fs.readFile(new URL('images/1-125.png',base)));
for(const [key,value]of annotationFiles(fixture,image,true))entries.set(key,value);
let rejected=false;try{validateShapes(fixture,[{id:'bad',label:'字',box:[-1,0,2,3]}]);}catch{rejected=true;}if(!rejected)throw Error('Invalid rectangle was accepted');
await fs.writeFile(process.argv[2],Buffer.from(await makeZip(entries).arrayBuffer()));
console.log(`Exported ${manifest.files.length} source documents and Unicode edit fixture.`);
