"""Explicit, reversible order-only review for the local corpus."""
from pathlib import Path
import json,hashlib,re,os,uuid,datetime,csv,io,copy
B=Path('/Users/shengyijun/CVPR2026/MCHDoc/page-level/Silk_V2')
BACK=Path('/Users/shengyijun/标注/数据筛查与备份_20260928/备份')
def load(p):return json.loads(p.read_text())
def enc(v):return json.dumps(v,ensure_ascii=False,indent=2).encode()
def sha(v):return hashlib.sha256(v).hexdigest()
def atomic(p,b):
 p.parent.mkdir(parents=True,exist_ok=True);t=p.with_name(p.name+'.'+uuid.uuid4().hex+'.tmp')
 try:
  with t.open('wb') as f:f.write(b);f.flush();os.fsync(f.fileno())
  os.replace(t,p)
 finally:
  if t.exists():t.unlink()
def state(base):
 p=base/'草稿/_order-review.json'
 return load(p) if p.exists() else {'revision':0,'items':{}}
def one(rows,n):return next(r for r in rows if r['name']==n)
def key(s):return (s['label'],tuple(s['box']))
def permutation(current,target):
 buckets={}
 for i,s in enumerate(current):buckets.setdefault(key(s),[]).append(i)
 result=[]
 for s in target:
  k=key(s)
  if not buckets.get(k):raise ValueError('文字或框已修改，对照版本已过期，请重新生成对照后复核')
  result.append(buckets[k].pop(0))
 if any(buckets.values()):raise ValueError('标注数量已变更，对照版本已过期')
 return result

def apply(base,data):
 w=base/'dist';idx=load(w/'order/index.json');n=data.get('name');choice=data.get('choice')
 if n not in {r['name'] for r in idx['files']} or choice not in ('before','after'):raise ValueError('无效图片或复核选择')
 if data.get('version')!=idx['version']:raise ValueError('对照版本已更新，请刷新后复核')
 st=state(base)
 if data.get('revision')!=st['revision']:raise ValueError('其他窗口已更新复核记录，请刷新再试')
 comp=load(w/f'order/data/{n}.json');target=[comp['before'][i] for i in (comp['after'] if choice=='after' else range(len(comp['before'])))];q=B/'质量检查'
 details=load(q/'逐文件检查明细.json');f=one(details,n);current=f['shapes'];perm=permutation(current,target);pos={v:i for i,v in enumerate(perm)}
 src=Path(f['annotation']);raw=src.read_bytes();cp=B/f'coordinate/{n}.txt';gp=B/f'gt-label/{n}.txt';lines=cp.read_text().splitlines()
 if sha(raw)!=f['annotation_sha256'] or gp.read_text()!=''.join(s['label'] for s in current) or [list(map(float,l.split(','))) for l in lines]!=[s['box'] for s in current]:raise ValueError('源标注或 GT 已发生更改，请重新同步后复核')
 changes={};old={}
 def stage(p,b):
  prev=p.read_bytes() if p.exists() else None
  if prev!=b:changes[p]=b;old[p]=prev
 def js(p,v):stage(p,enc(v))
 if src.suffix.lower()=='.xml':
  text=raw.decode();blocks=re.findall(r'<object>.*?</object>',text,re.S)
  if len(blocks)!=len(current):raise ValueError('XML 框数量不一致')
  it=iter(blocks[i] for i in perm);newraw=re.sub(r'<object>.*?</object>',lambda m:next(it),text,flags=re.S).encode()
 else:
  obj=json.loads(raw)
  if len(obj['shapes'])!=len(current):raise ValueError('JSON 框数量不一致')
  obj['shapes']=[obj['shapes'][i] for i in perm];newraw=enc(obj)
 gt=''.join(s['label'] for s in target).encode();coords=('\n'.join(lines[i] for i in perm)+'\n').encode();stage(src,newraw);stage(gp,gt);stage(cp,coords)
 stamp=datetime.datetime.now().astimezone().isoformat(timespec='seconds');decision={'choice':choice,'updatedAt':stamp,'version':idx['version'],'name':n}
 def remap(r):
  for k in ['out_of_bounds','invalid_boxes','empty_labels','multi_character_labels','unknown_labels','exact_duplicates','overlap_pairs']:
   for v in r.get(k,[]):
    if isinstance(v,dict):
     if 'index' in v:v['index']=pos[v['index']-1]+1
     if 'indices' in v:v['indices']=[pos[i-1]+1 for i in v['indices']]
  for k in ['order_candidates','raw_order_candidates']:
   if k in r:r[k]=[[pos[i-1]+1 for i in pair] for pair in r[k]]
 remap(f);f['shapes']=[current[i] for i in perm]
 for i,s in enumerate(f['shapes'],1):s['index']=i
 f['annotation_sha256']=sha(newraw);f['output_sha256'].update({'gt-label':sha(gt),'coordinate':sha(coords)});f['orderReviewDecision']=decision;js(q/'逐文件检查明细.json',details)
 m=load(q/'提取来源与校验清单.json');one(m,n).update(annotation_sha256=sha(newraw),output_sha256=f['output_sha256'],orderReviewDecision=decision);js(q/'提取来源与校验清单.json',m)
 gi=load(q/'GT字符区间索引.json');g=one(gi['files'],n);spans=g['spans'];offset=0;out=[]
 for j,i in enumerate(perm,1):
  v=dict(spans[i]);v.update(coordinate_line=j,start=offset,end=offset+len(current[i]['label']));offset=v['end'];out.append(v)
 g.update(spans=out,codepoint_count=offset,gt_sha256=sha(gt));js(q/'GT字符区间索引.json',gi)
 pp=q/'问题清单.json'
 if pp.exists():
  p=load(pp);r=next((r for r in p if r['name']==n),None)
  if r:remap(r);r['orderReviewDecision']=decision;js(pp,p)
 ap=w/f'all/data/{n}.json';a=load(ap);a.update(boxes=target,gt=gt.decode(),orderReviewDecision=decision);js(ap,a)
 ai=load(w/'all/index.json');one(ai['files'],n)['orderReviewDecision']=decision;js(w/'all/index.json',ai)
 ep=w/f'data/{n}.json'
 if ep.exists():
  ed=load(ep)
  draft=base/f'草稿/{n}.json'
  if draft.exists():
   dr=load(draft)
   if dr.get('shapes')!=ed['shapes']:raise ValueError('此页存在编辑草稿，请先保存并导入草稿，再重新生成顺序对照')
  eperm=permutation(ed['shapes'],target);ed['shapes']=[ed['shapes'][i] for i in eperm];ed.update(sourceSha256=sha(newraw),orderReviewDecision=decision,annotationImportedAt=stamp,revision=ed.get('revision',0)+1);js(ep,ed)
  if draft.exists():dr.update(shapes=ed['shapes'],revision=ed['revision'],orderReviewDecision=decision);js(draft,dr)
  em=load(w/'data/manifest.json');one(em['files'],n).update(sourceSha256=sha(newraw),annotationImportedAt=stamp,orderReviewDecision=decision);js(w/'data/manifest.json',em)
 st['items'][n]=decision;st['revision']+=1;js(base/'草稿/_order-review.json',st)
 # Back up all changed files before any corpus write. Roll back a failed transaction.
 BACK.mkdir(parents=True,exist_ok=True);rows=[]
 for p,b in old.items():
  if b is not None:
   h=sha(b);dest=BACK/(h[:16]+'_'+p.name)
   if dest.exists() and sha(dest.read_bytes())!=h:raise ValueError('备份校验失败')
   if not dest.exists():atomic(dest,b)
   rows.append([str(p),dest.name,h,'顺序复核按钮 '+n])
 with (BACK/'文件索引.csv').open('a',newline='') as fp:csv.writer(fp).writerows(rows)
 written=[]
 try:
  for p,b in changes.items():atomic(p,b);written.append(p)
 except Exception:
  for p in reversed(written):
   if old[p] is None:p.unlink(missing_ok=True)
   else:atomic(p,old[p])
  raise
 return st
