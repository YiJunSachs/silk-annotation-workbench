import {annotationFiles,makeZip,validateShapes,exportReadme} from './export-formats.mjs';
const root = new URL('.',location.href);
export let browserMode = !['127.0.0.1','localhost','[::1]'].includes(location.hostname);
let readyPromise,dbPromise,manifestPromise;
const clone = value => structuredClone(value);
async function staticJson(path){const r=await fetch(new URL(path.replace(/^\//,''),root),{cache:'no-cache'});if(!r.ok)throw Error('读取失败：'+path);return r.json();}
export function ready(){return readyPromise ??= (async()=>{if(!browserMode){try{const r=await fetch('/api/manifest');const m=await r.json();if(!r.ok||!Array.isArray(m.files))browserMode=true;}catch{browserMode=true;}}return browserMode;})();}
function database(){return dbPromise ??= new Promise((resolve,reject)=>{const r=indexedDB.open('silk-annotations:'+root.pathname,1);r.onupgradeneeded=()=>r.result.createObjectStore('records');r.onsuccess=()=>resolve(r.result);r.onerror=()=>reject(Error('浏览器无法保存草稿，请允许此网站使用本地存储'));});}
async function read(key){const db=await database();return new Promise((resolve,reject)=>{const r=db.transaction('records').objectStore('records').get(key);r.onsuccess=()=>resolve(r.result);r.onerror=()=>reject(r.error);});}
function staleDraft(draft,source){
  if(!draft||!source?.importedAnnotation&&!source?.annotationImportedAt)return false;
  if(draft.baseSourceSha256)return draft.baseSourceSha256!==source.sourceSha256;
  return true; // Drafts saved before source-version tracking belong to the previous annotation.
}
async function oldDraft(name,source){
  const key='doc:'+name,current=await read(key);
  if(staleDraft(current,source))return current;
  const latest=await read('archived-latest:'+key);
  return latest?read(latest.key):undefined;
}
async function write(key,revision,value,source){
  const db=await database();
  return new Promise((resolve,reject)=>{const tx=db.transaction('records','readwrite'),store=tx.objectStore('records'),r=store.get(key);let result,error;
    r.onsuccess=()=>{const previous=r.result,stale=staleDraft(previous,source);
      if((previous?.revision??0)!==revision&&!(stale&&revision===0)){error=Error('此记录已在其他窗口更新，请刷新后继续；未覆盖已有草稿');tx.abort();return;}
      if(stale){const archived='archived-doc:'+key+':'+Date.now();store.put(previous,archived);store.put({key:archived},'archived-latest:'+key);}
      result={...clone(value),revision:stale?1:revision+1,updatedAt:new Date().toISOString()};store.put(result,key);};
    tx.oncomplete=()=>resolve(result);tx.onabort=()=>reject(error||tx.error||Error('草稿保存失败'));tx.onerror=()=>{error=tx.error;};
  });
}
function originalManifest(){return manifestPromise ??= staticJson('data/manifest.json');}
async function original(name){const m=await originalManifest();if(!m.files.some(f=>f.name===name))throw Error('不存在的图片编号');return staticJson('data/'+encodeURIComponent(name)+'.json');}
async function annotationDocument(name){const source=await original(name),draft=await read('doc:'+name);const old=await oldDraft(name,source);return {...source,...(staleDraft(draft,source)?{}:draft),oldDraftAvailable:!!old};}
export async function api(path,data){
  await ready();
  if(!browserMode){const r=await fetch(path,data?{method:'POST',headers:{'Content-Type':'application/json','X-Silk-Editor':'1'},body:JSON.stringify(data)}:{});const result=await r.json();if(!r.ok)throw Error(result.error||'请求失败');return result;}
  if(path.startsWith('/data/'))return staticJson(path);
  if(path==='/api/manifest'){
    const m=clone(await originalManifest());
    await Promise.all(m.files.map(async f=>{const d=await read('doc:'+f.name),active=staleDraft(d,f)?null:d;f.revision=active?.revision??0;f.reviewed=active?.reviewed??f.reviewed??false;if(active)f.boxes=active.shapes.length;}));
    m.outputPath='当前浏览器草稿；标注文件通过下载保存';return m;
  }
  if(path.startsWith('/api/doc/'))return annotationDocument(decodeURIComponent(path.slice('/api/doc/'.length)));
  if(path.startsWith('/api/old-draft/')){
    const name=decodeURIComponent(path.slice('/api/old-draft/'.length)),source=await original(name),draft=await oldDraft(name,source);
    if(!draft)throw Error('没有可下载的旧草稿');return {name,...draft};
  }
  if(path==='/api/discussion'){
    if(!data)return await read('discussion')||{revision:0,items:{}};
    const m=await staticJson('data/fragments.json'),names=new Set(m.files.map(f=>f.name));
    if(!data.items||typeof data.items!=='object'||Object.entries(data.items).some(([n,v])=>!names.has(n)||!['待讨论','建议保留','建议剔除','补标后保留'].includes(v.decision)||typeof v.note!=='string'||v.note.length>4000))throw Error('讨论记录格式无效');
    return write('discussion',data.revision,{items:data.items});
  }
  if(path==='/api/draft'){
    const d=await original(data.name);validateShapes(d,data.shapes);
    if(data.baseSourceSha256!==d.sourceSha256)throw Error('标注源文件已更新，请刷新页面后再编辑；旧草稿仍保存在浏览器中');
    const ids=new Set(data.shapes.map(s=>s.id));if(!Array.isArray(data.resolved)||data.resolved.some(id=>!ids.has(id))||typeof data.reviewed!=='boolean')throw Error('复核状态无效');
    return write('doc:'+data.name,data.revision,{shapes:data.shapes,resolved:data.resolved,reviewed:data.reviewed,baseSourceSha256:d.sourceSha256},d);
  }
  if(path==='/api/save'){
    const d=await annotationDocument(data.name);if(d.revision!==data.revision)throw Error('此图已在其他窗口更新，请刷新后再导出');
    const blob=await exportBlob(data.name,'zip');downloadBlob(blob,'Silk_annotations_'+data.name+'.zip');
    return {name:data.name,boxes:d.shapes.length,path:'浏览器下载目录（ZIP 标注包）',downloaded:true};
  }
  throw Error('未知操作');
}
export async function exportBlob(scope,format,onProgress=()=>{}){
  await ready();
  if(!browserMode){const r=await fetch('/api/export?scope='+encodeURIComponent(scope)+'&format='+format);if(!r.ok)throw Error((await r.json()).error);return r.blob();}
  const m=await api('/api/manifest');let names;
  if(scope==='all')names=m.files.map(f=>f.name);
  else if(scope==='reviewed')names=m.files.filter(f=>f.reviewed).map(f=>f.name);
  else if(scope==='edited')names=m.files.filter(f=>f.revision>0).map(f=>f.name);
  else names=m.files.filter(f=>f.name===scope).map(f=>f.name);
  if(!names.length)throw Error('所选范围没有可导出的图片');
  if(!['zip','json','xml'].includes(format))throw Error('未知导出格式');
  const entries=new Map(),review=[];
  for(const [index,name] of names.entries()){onProgress(`正在打包 ${index+1}/${names.length}：${name}`);const d=await annotationDocument(name),r=await fetch(new URL(d.image,root),{signal:AbortSignal.timeout(45000)});if(!r.ok)throw Error('原图下载失败：'+name);const image=new Uint8Array(await r.arrayBuffer());const files=annotationFiles(d,image,format==='json');
    if(format!=='zip')return new Blob([files.get(`annotations-${format}/${name}.${format}`)],{type:format==='json'?'application/json':'application/xml'});
    for(const [key,value]of files)entries.set(key,value);review.push({name,reviewed:d.reviewed,revision:d.revision,resolved:d.resolved||[]});
  }
  entries.set('README.txt',exportReadme);entries.set('review-status.json',JSON.stringify(review,null,2));return makeZip(entries);
}
export function downloadBlob(blob,filename){const u=URL.createObjectURL(blob),a=document.createElement('a');a.href=u;a.download=filename;a.click();setTimeout(()=>URL.revokeObjectURL(u),60000);}

// Read durable browser drafts directly: no image or annotation network requests.
export async function exportReviewedDrafts(){
 const db=await database();
 const records=await new Promise((resolve,reject)=>{const tx=db.transaction('records'),store=tx.objectStore('records'),items=[],request=store.openCursor();
 request.onsuccess=()=>{const cursor=request.result;if(!cursor)return;const key=String(cursor.key),value=cursor.value;if(key.startsWith('doc:')&&value.reviewed===true)items.push({name:key.slice(4),...clone(value)});cursor.continue();};
 tx.oncomplete=()=>resolve(items);tx.onabort=()=>reject(tx.error||Error('读取复核草稿失败'));tx.onerror=()=>reject(tx.error||Error('读取复核草稿失败'));});
 if(!records.length)throw Error('此浏览器尚无已完成复核的草稿');
 records.sort((a,b)=>a.name.localeCompare(b.name,undefined,{numeric:true}));
 return new Blob([JSON.stringify({schema:'silk-reviewed-drafts-v1',exportedAt:new Date().toISOString(),records},null,2)],{type:'application/json'});
}
