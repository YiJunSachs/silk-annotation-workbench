// Only the loopback server can mutate the official local corpus.
export function installRemoval({getName,beforePreview=async()=>true}){
 const button=document.createElement('button');button.type='button';button.textContent='从正式数据集剔除并备份';button.id='removeDataset';button.style.cssText='color:#a5262b;border:1px solid #cf9d9f;background:#fff5f5;padding:8px 12px;border-radius:6px;margin:4px;cursor:pointer';
 (document.querySelector('.review-actions')||document.querySelector('.document-bar')||document.querySelector('.heading')||document.querySelector('header')).append(button);
 const dialog=document.createElement('dialog');dialog.id='removeDatasetDialog';dialog.style.cssText='max-width:620px;width:calc(100% - 48px);border:1px solid #d5dbe5;border-radius:12px;padding:24px;color:#172b45';
 dialog.innerHTML='<h2>从正式数据集剔除并备份</h2><p class="removal-message" role="status" style="white-space:pre-wrap"></p><details hidden><summary>将移除的文件</summary><pre style="white-space:pre-wrap;overflow-wrap:anywhere;max-height:180px;overflow:auto"></pre></details><label class="removal-label" hidden>输入当前图片编号确认：<input class="removal-confirm" autocomplete="off" style="margin:8px;width:120px"></label><p><button class="removal-cancel" type="button">取消</button> <button class="removal-apply" type="button" disabled>确认剔除并备份</button></p>';
 document.body.append(dialog);const message=dialog.querySelector('.removal-message'),confirm=dialog.querySelector('.removal-confirm'),apply=dialog.querySelector('.removal-apply'),cancel=dialog.querySelector('.removal-cancel');let preview=null,working=false;
 async function request(path,data){const r=await fetch(path,{cache:'no-store',...(data?{method:'POST',headers:{'Content-Type':'application/json','X-Silk-Editor':'1'},body:JSON.stringify(data)}:{})});let d;try{d=await r.json();}catch{throw Error('本机服务尚未更新，请重启工作台服务。');}if(!r.ok)throw Error(d.error||'操作失败');return d;}
 // Keep editing shortcuts out of the confirmation dialog.
 window.addEventListener('keydown',e=>{if(dialog.open)e.stopImmediatePropagation();},true);
 dialog.addEventListener('cancel',e=>{if(working)e.preventDefault();});cancel.onclick=()=>{if(!working)dialog.close();};confirm.oninput=()=>{apply.disabled=working||!preview||confirm.value.trim()!==preview.name;};
 button.onclick=async()=>{
  if(working)return;preview=null;confirm.value='';apply.disabled=true;dialog.querySelector('details').hidden=true;dialog.querySelector('.removal-label').hidden=true;
  if(!['127.0.0.1','localhost'].includes(location.hostname)){message.textContent='正式数据集保存在你的电脑上。请在本机工作台打开同一图片，使用此按钮剔除并备份。公网操作不会修改本机文件。';dialog.showModal();return;}
  const name=getName();if(!name){message.textContent='请先选择并加载一张图片。';dialog.showModal();return;}
  button.disabled=true;
  try{if(!await beforePreview())return;message.textContent='正在核对 '+name+' 的文件…';dialog.showModal();preview=await request('/api/removal-preview?name='+encodeURIComponent(name));
   message.textContent=`当前图片：${preview.name} · ${preview.boxes} 个框\n将剔除 ${preview.fileCount} 个相关文件，包括源标注、图片、坐标、GT、本机草稿及工作台副本。剔除后剩 ${preview.remainingImages} 组。\n备份位置：${preview.backupPath}\n本机列表会同步更新。公网网站需另行发布同步。${preview.preservedSources?.length?'\n外部原始图片保留，不会删除：\n'+preview.preservedSources.join('\n'):''}`;
   dialog.querySelector('pre').textContent=preview.files.join('\n');dialog.querySelector('details').hidden=false;dialog.querySelector('.removal-label').hidden=false;confirm.focus();
  }catch(e){preview=null;message.textContent='无法开始剔除：'+e.message+'\n尚未移除任何文件。可关闭窗口后重试。';cancel.textContent='关闭';}finally{button.disabled=false;}
 };
 apply.onclick=async()=>{
  if(!preview||working||confirm.value.trim()!==preview.name)return;working=true;apply.disabled=true;cancel.disabled=true;confirm.disabled=true;message.textContent='正在备份并校验 '+preview.name+'，随后剔除…';
  try{const result=await request('/api/remove-dataset',{name:preview.name,confirmName:confirm.value.trim(),token:preview.token});
   message.textContent=`${result.name} 已剔除并备份。剩余 ${result.remainingImages} 组。\n恢复记录：${result.logPath}\n公网网站尚未自动同步。`;
   dialog.querySelector('.removal-label').hidden=true;dialog.querySelector('details').hidden=true;apply.hidden=true;cancel.textContent='完成，刷新列表';cancel.disabled=false;cancel.onclick=()=>{location.href=location.pathname;};dialog.oncancel=e=>{e.preventDefault();location.href=location.pathname;};
  }catch(e){message.textContent='剔除未完成：'+e.message+'\n请重新打开窗口核对最新状态。';preview=null;cancel.disabled=false;}
  finally{working=false;confirm.disabled=false;}
 };
}
