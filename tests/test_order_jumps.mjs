import assert from 'node:assert/strict';
import fs from 'node:fs';
import {detectJumps} from '../dist/order-jumps.js';
const read=n=>JSON.parse(fs.readFileSync(new URL('../dist/order/data/'+n+'.json',import.meta.url)));
for(const n of ['1-34','1-101','1-117','1-150']){const d=read(n);assert(detectJumps(d.before,d.before.map((_,i)=>i)).length>0,n+' old jumps');assert.equal(detectJumps(d.before,d.after).length,0,n+' repaired');}
const box=(x,y)=>({label:'字',box:[x,y,x+10,y+10]});
const correct=[...Array.from({length:8},(_,i)=>box(30-i*.3,i*15)),...Array.from({length:8},(_,i)=>box(10-i*.3,i*15))];assert.equal(detectJumps(correct,correct.map((_,i)=>i)).length,0);
const reversed=[...correct.slice(8),...correct.slice(0,8)];assert(detectJumps(reversed,reversed.map((_,i)=>i)).some(e=>e.type==='反向换列'));
const up=[box(20,0),box(20,45),box(20,15),box(20,60)];assert(detectJumps(up,[0,1,2,3]).some(e=>e.type==='同列向上回跳'));
console.log('PASS: repaired pages, tilted normal column transitions, reversed columns and upward jumps');
