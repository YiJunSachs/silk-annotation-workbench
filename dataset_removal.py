"""Local-only, previewed corpus removal with verified backups and rollback."""
from pathlib import Path
import json,re,hashlib,csv,datetime,uuid
from order_review import atomic,enc,load,sha
B=Path('/Users/shengyijun/CVPR2026/MCHDoc/page-level/Silk_V2')
R=Path('/Users/shengyijun/标注/数据筛查与备份_20260928')

def plan(base,name):
 if not isinstance(name,str) or not re.fullmatch(r'[12]-\d+',name):raise ValueError('图片编号无效')
 w=base/'dist';q=B/'质量检查';details=load(q/'逐文件检查明细.json');row=next((x for x in details if x['name']==name),None)
 if row is None:raise ValueError('该图片已不在正式数据集中，请刷新页面')
 before_count=len(details);before_boxes=sum(x['box_count'] for x in details);remaining=[x for x in details if x['name']!=name];count=len(remaining);boxes=sum(x['box_count'] for x in remaining)
 removed=[]
 for root in [B,w,base/'草稿',base/'保存结果']:
  if root.exists():
   for p in root.rglob('*'):
    if p.is_file() and p.stem==name:
     if p.is_symlink() or not p.resolve().is_relative_to(root.resolve()):raise ValueError('遇到链接文件，需人工核对后剔除')
     removed.append(p)
 for key in ['annotation','source_image']:
  src=Path(row[key])
  if src not in removed:raise ValueError('源文件不在安全剔除范围内：'+str(src))
 for folder in ['intact-img','coordinate','gt-label']:
  if not any(p.parent==B/folder for p in removed):raise ValueError('图片、坐标或 GT 不完整，请先核对')
 changes={}
 def stage(p,data):
  if p.read_bytes()!=data:changes[p]=data
 paths=[q/'逐文件检查明细.json',q/'提取来源与校验清单.json',q/'问题清单.json',q/'GT字符区间索引.json',B/'visualize/manifest.json',w/'all/index.json',w/'order/index.json',w/'data/manifest.json',w/'data/fragments.json',base/'保存结果/review-status.json']
 for p in paths:
  if not p.exists():continue
  d=load(p)
  if isinstance(d,list):d=[x for x in d if x.get('name')!=name]
  else:
   d['files']=[x for x in d['files'] if x.get('name')!=name]
   if 'images' in d:d['images']=len(d['files'])
   if 'boxes' in d:d['boxes']=sum(x.get('boxes',x.get('box_count',0)) for x in d['files'])
   if p==w/'order/index.json':d['changed']=sum(bool(x['moved']) for x in d['files']);d['review']=sum(bool(x['review']) for x in d['files'])
  stage(p,enc(d))
 stamp=datetime.datetime.now().astimezone().isoformat(timespec='seconds')
 for p in [w/'data/fragment-review-coverage.json',q/'全部168组顺序调整记录.json']:
  if not p.exists():continue
  d=load(p)
  for x in d['files']:
   if x['name']==name:x.update(removedFromDataset=True,removedAt=stamp,currentStatus='已剔除并备份')
  stage(p,enc(d))
 p=q/'统计汇总.json'
 if p.exists():
  d=load(p);d.update(images=count,boxes=boxes);d.setdefault('user_excluded_pages',[])
  if name not in d['user_excluded_pages']:d['user_excluded_pages'].append(name)
  for k in ['out_of_bounds','invalid_boxes','empty_labels','multi_character_labels','unknown_labels','exact_duplicates','overlap_pairs','order_candidates']:d[k]={'files':sum(bool(x.get(k)) for x in remaining),'items':sum(len(x.get(k,[])) for x in remaining)}
  if 'coordinate_order_adjustment' in d:
   a=d['coordinate_order_adjustment'];old=row.get('order_adjustment',{});a['processed']=count
   for k,value in [('changed',bool(old.get('moved'))),('renumbered',old.get('moved',0)),('review_files',bool(old.get('review_required')))]:a[k]=max(0,a.get(k,0)-value)
  stage(p,enc(d))
 for p in [base/'草稿/_order-review.json',base/'草稿/_discussion.json']:
  if p.exists():
   d=load(p)
   if name in d.get('items',{}):d['items'].pop(name);d['revision']+=1;stage(p,enc(d))
 for p in [q/'质检报告.html',B/'visualize/index.html']:
  if not p.exists():continue
  s=p.read_text()
  if p.parent==q:s=re.sub(r'<tr\b[^>]*>.*?</tr>',lambda m:'' if re.search(r'(?<![\d-])'+re.escape(name)+r'(?!\d)',m[0]) else m[0],s,flags=re.S)
  else:s=re.sub(r'<a\b[^>]*class="card"[^>]*>.*?</a>',lambda m:'' if 'data-name="'+name+'"' in m[0] else m[0],s,flags=re.S)
  s=re.sub(r'(?<!\d)'+str(before_count)+r'(?=\s*(?:张|组|幅))',str(count),s);s=s.replace(f'{before_boxes:,}',f'{boxes:,}');s=re.sub(r'(?<!\d)'+str(before_boxes)+r'(?!\d)',str(boxes),s);stage(p,s.encode())
 # Remove old next/previous links without guessing a new reading sequence.
 for p in (B/'visualize/pages').glob('*.html'):
  if p in removed:continue
  s=p.read_text();new=re.sub(r'<a\b[^>]*href="'+re.escape(name)+r'\.html"[^>]*>.*?</a>','',s)
  if new!=s:stage(p,new.encode())
 oldbytes={p:p.read_bytes() for p in list(changes)+removed}
 token=sha(enc([(str(p),sha(b)) for p,b in sorted(oldbytes.items(),key=lambda x:str(x[0]))]))
 summary={'name':name,'boxes':row['box_count'],'remainingImages':count,'remainingBoxes':boxes,'fileCount':len(removed),'backupPath':str(R/'备份'),'token':token,'files':[str(p) for p in removed]}
 return summary,changes,removed,oldbytes

def preview(base,name):return plan(base,name)[0]

def apply(base,data):
 n=data.get('name');summary,changes,removed,oldbytes=plan(base,n)
 if data.get('confirmName')!=n or data.get('token')!=summary['token']:raise ValueError('确认信息已过期或编号不匹配，请重新打开剔除窗口')
 backup=R/'备份';backup.mkdir(parents=True,exist_ok=True);records=[]
 for p,b in oldbytes.items():
  h=sha(b);dest=backup/(h[:16]+'_'+p.name)
  if not dest.exists():atomic(dest,b)
  if sha(dest.read_bytes())!=h:raise ValueError('备份校验失败，未剔除任何文件')
  records.append({'path':str(p),'backup':str(dest),'sha256':h,'action':'remove' if p in removed else 'update'})
 # Durable recovery manifest exists before any deletion, including after a process crash.
 stamp=datetime.datetime.now().astimezone().isoformat();log=R/'筛查记录'/(n+'_工作台剔除_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:6]+'.json')
 report={**summary,'date':stamp,'status':'prepared','files':records};atomic(log,enc(report))
 with (backup/'文件索引.csv').open('a',newline='') as f:csv.writer(f).writerows([[r['path'],Path(r['backup']).name,r['sha256'],'工作台剔除 '+n] for r in records])
 touched=[]
 try:
  for p,b in changes.items():atomic(p,b);touched.append(p)
  for p in removed:p.unlink();touched.append(p)
  report['status']='completed';atomic(log,enc(report))
 except Exception:
  for p in reversed(touched):atomic(p,oldbytes[p])
  report['status']='rolled_back';atomic(log,enc(report));raise
 return {**summary,'logPath':str(log),'status':'completed'}
