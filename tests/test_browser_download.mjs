import assert from 'node:assert/strict';
globalThis.location = new URL('https://example.test/silk/');
let clicked=false, anchor, revoke, timer;
globalThis.document = {createElement(tag){assert.equal(tag,'a');return anchor={click(){clicked=true;}};}};
const originalTimer=globalThis.setTimeout,originalRevoke=URL.revokeObjectURL;
globalThis.setTimeout=(fn,delay)=>{assert.equal(delay,60000);timer=fn;};
URL.revokeObjectURL=url=>{revoke=url;originalRevoke(url);};
try {
 const {downloadBlob}=await import('../dist/browser-api.js');
 downloadBlob(new Blob(['reviewed annotations']), 'Silk_annotations_reviewed.zip');
 assert.equal(clicked,true);assert.equal(anchor.download,'Silk_annotations_reviewed.zip');
 assert.match(anchor.href,/^blob:/);assert.equal(revoke,undefined);timer();assert.equal(revoke,anchor.href);
 console.log('PASS: browser download creates and clicks an anchor, then revokes its blob URL.');
} finally {globalThis.setTimeout=originalTimer;URL.revokeObjectURL=originalRevoke;}
