import assert from 'node:assert/strict';
globalThis.location=new URL('https://example.test/silk/');
const m={files:[{name:'1-32',reviewed:true,boxes:309},{name:'1-50',reviewed:false,boxes:887},{name:'1-125',reviewed:true,boxes:523}]};
globalThis.fetch=async()=>({ok:true,json:async()=>structuredClone(m)});
globalThis.indexedDB={open(){const r={};queueMicrotask(()=>{r.result={transaction(){return {objectStore(){return {get(key){const q={};queueMicrotask(()=>{q.result=key==='doc:1-125'?{reviewed:false,revision:3,shapes:[{}]}:undefined;q.onsuccess();});return q;}};}};}};r.onsuccess();});return r;}};
const {api}=await import('../dist/browser-api.js');const actual=await api('/api/manifest');
assert.equal(actual.files[0].reviewed,true);assert.equal(actual.files[1].reviewed,false);assert.equal(actual.files[2].reviewed,false);assert.equal(actual.files[2].boxes,1);
console.log('PASS: imported review status survives a fresh browser; explicit local draft status takes precedence.');
