#!/usr/bin/env python3
"""Local-only Silk annotation editor; explicit order review can update the source corpus."""
from http.server import ThreadingHTTPServer,SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlsplit,unquote,parse_qs
import argparse,json,threading,math,io,zipfile,base64,shutil,os,uuid,xml.etree.ElementTree as ET,datetime
import order_review,dataset_removal
BASE=Path(__file__).resolve().parent;DIST=BASE/'dist';DRAFTS=BASE/'草稿';OUTPUT=BASE/'保存结果';LOCK=threading.RLock()
MANIFEST=json.loads((DIST/'data/manifest.json').read_text());NAMES={r['name'] for r in MANIFEST['files']}
def now():return datetime.datetime.now().astimezone().isoformat(timespec='seconds')
def atomic(path,data):
 path.parent.mkdir(parents=True,exist_ok=True);temp=path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
 try:
  with temp.open('wb') as f:f.write(data);f.flush();os.fsync(f.fileno())
  os.replace(temp,path)
 finally:
  if temp.exists():temp.unlink()
def encoded(obj):return json.dumps(obj,ensure_ascii=False,indent=2).encode('utf-8')
def original(name):
 if name not in NAMES:raise ValueError('不存在的图片编号')
 return json.loads((DIST/'data'/(name+'.json')).read_text())
def document(name):
 base=original(name);p=DRAFTS/(name+'.json')
 if p.exists():base.update(json.loads(p.read_text()))
 return base
def validated(name,data):
 base=original(name);shapes=data.get('shapes');ids=set();source_indices={s.get('sourceIndex') for s in base['shapes'] if s.get('sourceIndex') is not None}
 if not isinstance(shapes,list) or len(shapes)>10000:raise ValueError('标注数量不合法')
 for s in shapes:
  if not isinstance(s,dict) or not isinstance(s.get('id'),str) or not s['id'] or len(s['id'])>160 or s['id'] in ids:raise ValueError('标注ID重复或无效')
  ids.add(s['id'])
  if not isinstance(s.get('label'),str) or not s['label'].strip() or len(s['label'])>200 or any(c in s['label'] for c in '\r\n\x00'):raise ValueError('每个框需填写有效文字，无法释读请填 □；不能包含换行')
  if any(ord(c)<32 and c!='\t' for c in s['label']):raise ValueError('文字包含无效控制字符')
  b=s.get('box')
  if not isinstance(b,list) or len(b)!=4 or not all(isinstance(x,(int,float)) and not isinstance(x,bool) and math.isfinite(x) for x in b):raise ValueError('坐标必须是4个有限数值')
  if not (0<=b[0]<b[2]<=base['width'] and 0<=b[1]<b[3]<=base['height']):raise ValueError('矩形框超出图片范围或面积为零')
  si=s.get('sourceIndex')
  if si is not None and (not isinstance(si,int) or isinstance(si,bool) or si not in source_indices):raise ValueError('原始序号无效')
 if not isinstance(data.get('reviewed',False),bool):raise ValueError('审核状态无效')
 resolved=data.get('resolved',[])
 if not isinstance(resolved,list) or any(not isinstance(x,str) or x not in ids for x in resolved):raise ValueError('已处理标记无效')
 return {'resolved':list(dict.fromkeys(resolved)),'shapes':[{'id':s['id'],'sourceIndex':s.get('sourceIndex'),'label':s['label'],'box':s['box']} for s in shapes],'reviewed':data.get('reviewed',False)}
def artifacts(doc,embed=False):
 n=doc['name'];w,h=doc['width'],doc['height'];sh=doc['shapes'];image=(DIST/'images'/(n+'.png')).read_bytes()
 labelme={'version':'5.5.0','flags':{},'shapes':[{'label':s['label'],'points':[[s['box'][0],s['box'][1]],[s['box'][2],s['box'][3]]],'group_id':None,'description':'','shape_type':'rectangle','flags':{}} for s in sh],'imagePath':(n+'.png' if embed else '../intact-img/'+n+'.png'),'imageData':base64.b64encode(image).decode() if embed else None,'imageHeight':h,'imageWidth':w}
 xml=ET.Element('annotation');ET.SubElement(xml,'folder').text='intact-img';ET.SubElement(xml,'filename').text=n+'.png';ET.SubElement(xml,'path').text='../intact-img/'+n+'.png';source=ET.SubElement(xml,'source');ET.SubElement(source,'database').text='Silk_V2';size=ET.SubElement(xml,'size')
 for k,v in [('width',w),('height',h),('depth',3)]:ET.SubElement(size,k).text=str(v)
 ET.SubElement(xml,'segmented').text='0'
 spans=[];start=0
 for i,s in enumerate(sh,1):
  ob=ET.SubElement(xml,'object');ET.SubElement(ob,'name').text=s['label'];ET.SubElement(ob,'pose').text='Unspecified';ET.SubElement(ob,'truncated').text='0';ET.SubElement(ob,'difficult').text='0';bnd=ET.SubElement(ob,'bndbox');b=s['box']
  # Pascal VOC integer, 1-based inclusive; editor/LabelMe use 0-based continuous pixel edges.
  for k,v in zip(['xmin','ymin','xmax','ymax'],[min(w,math.floor(b[0])+1),min(h,math.floor(b[1])+1),math.ceil(b[2]),math.ceil(b[3])]):ET.SubElement(bnd,k).text=str(v)
  spans.append({'coordinate_line':i,'start':start,'end':start+len(s['label']),'source_index':s.get('sourceIndex'),'id':s['id']});start+=len(s['label'])
 ET.indent(xml,space='  ')
 return {f'annotations-json/{n}.json':encoded(labelme),f'annotations-xml/{n}.xml':ET.tostring(xml,encoding='utf-8',xml_declaration=True),f'intact-img/{n}.png':image,f'coordinate/{n}.txt':('\n'.join(','.join(str(v) for v in s['box']) for s in sh)+ ('\n' if sh else '')).encode(),f'gt-label/{n}.txt':''.join(s['label'] for s in sh).encode(),f'gt-index/{n}.json':encoded({'name':n,'codepoint_count':start,'spans':spans})}
README='Silk 标注工作台导出\nannotations-json：LabelMe 矩形标注，imagePath 指向 ../intact-img。\nannotations-xml：Pascal VOC，整数、1起始闭区间；从编辑器0起始像素边界取外接整数框，xmin/ymin=floor+1，xmax/ymax=ceil。\ncoordinate：0起始原图像素边界，保留浮点精度，每行xmin,ymin,xmax,ymax，与JSON一致。\ngt-label：按框顺序连续拼接，无换行；多字标签不拆分。\ngt-index：Unicode码点区间与框顺序对应。\n保存只写入本编辑器的保存结果，不会覆盖原Silk_V2数据。\n'
class Handler(SimpleHTTPRequestHandler):
 def __init__(self,*args,**kw):super().__init__(*args,directory=str(DIST),**kw)
 def log_message(self,fmt,*args):print(self.log_date_time_string(),fmt%args,flush=True)
 def end_headers(self):self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.send_header('Referrer-Policy','no-referrer');super().end_headers()
 def reply(self,data,status=200,ctype='application/json; charset=utf-8',filename=None):
  if not isinstance(data,bytes):data=encoded(data)
  self.send_response(status);self.send_header('Content-Type',ctype);self.send_header('Content-Length',str(len(data)))
  if filename:self.send_header('Content-Disposition','attachment; filename="'+filename+'"')
  self.end_headers();self.wfile.write(data)
 def host_ok(self):return self.headers.get('Host') in {f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}'}
 def do_GET(self):
  if not self.host_ok():return self.reply({'error':'无效访问地址'},403)
  u=urlsplit(self.path);path=unquote(u.path)
  try:
   if path=='/api/removal-preview':
    with LOCK:return self.reply(dataset_removal.preview(BASE,parse_qs(u.query).get('name',[''])[0]))
   if path=='/api/order-review':
    with LOCK:return self.reply(order_review.state(BASE))
   if path=='/api/discussion':
    p=DRAFTS/'_discussion.json'
    with LOCK:d=json.loads(p.read_text()) if p.exists() else {'revision':0,'items':{}}
    return self.reply(d)
   if path=='/api/manifest':
    with LOCK:
     result=json.loads(json.dumps(MANIFEST));result['outputPath']=str(OUTPUT)
     for r in result['files']:
      d=document(r['name']);r.update(revision=d['revision'],reviewed=d['reviewed'],boxes=len(d['shapes']),saved=(OUTPUT/'annotations-json'/(r['name']+'.json')).exists())
    return self.reply(result)
   if path.startswith('/api/doc/'):
    with LOCK:d=document(path.rsplit('/',1)[-1])
    return self.reply(d)
   if path=='/api/export':
    qs=parse_qs(u.query);scope=qs.get('scope',['all'])[0];fmt=qs.get('format',['zip'])[0]
    with LOCK:
     names=[scope] if scope in NAMES else [r['name'] for r in MANIFEST['files'] if scope=='all' or (scope=='reviewed' and document(r['name'])['reviewed']) or (scope=='edited' and document(r['name'])['revision']>0)]
     if not names:raise ValueError('当前范围没有可导出的图片')
     if fmt in ['json','xml']:
      if len(names)!=1:raise ValueError('单文件格式仅支持当前图片')
      n=names[0];parts=artifacts(document(n),embed=fmt=='json');key=f'annotations-{fmt}/{n}.{fmt}';return self.reply(parts[key],ctype='application/json' if fmt=='json' else 'application/xml',filename=n+'.'+fmt)
     if fmt!='zip':raise ValueError('不支持的导出格式')
     b=io.BytesIO()
     with zipfile.ZipFile(b,'w',zipfile.ZIP_DEFLATED) as z:
      for n in names:
       for file,content in artifacts(document(n)).items():z.writestr(file,content)
      z.writestr('README.txt',README);z.writestr('review-status.json',encoded([{'name':n,'reviewed':document(n)['reviewed'],'revision':document(n)['revision']} for n in names]))
    return self.reply(b.getvalue(),ctype='application/zip',filename='Silk_annotations_'+str(len(names))+'.zip')
   if path.startswith('/api/'):return self.reply({'error':'接口不存在'},404)
   if path=='/':self.path='/index.html'
   return super().do_GET()
  except (ValueError,KeyError,TypeError) as e:return self.reply({'error':str(e)},400)
  except Exception as e:print('ERROR',repr(e),flush=True);return self.reply({'error':'读取失败，请检查本地服务终端'},500)
 def do_POST(self):
  if not self.host_ok() or self.headers.get('X-Silk-Editor')!='1':return self.reply({'error':'拒绝外部请求'},403)
  origin=self.headers.get('Origin')
  if origin and origin not in {f'http://127.0.0.1:{self.server.server_port}',f'http://localhost:{self.server.server_port}'}:return self.reply({'error':'拒绝跨站写入'},403)
  try:
   length=int(self.headers.get('Content-Length','0'))
   if not 0<length<=8000000:raise ValueError('请求大小无效')
   data=json.loads(self.rfile.read(length));path=urlsplit(self.path).path
   if path=='/api/discussion':
    with LOCK:
     p=DRAFTS/'_discussion.json';old=json.loads(p.read_text()) if p.exists() else {'revision':0,'items':{}}
     if data.get('revision')!=old['revision']:return self.reply({'error':'Discussion changed in another window. Refresh first.'},409)
     names={x['name'] for x in json.loads((DIST/'data/fragments.json').read_text())['files']};items=data.get('items')
     if not isinstance(items,dict) or not set(items)<=names:raise ValueError('Invalid discussion names')
     for v in items.values():
      if not isinstance(v,dict) or v.get('decision') not in ['待讨论','建议保留','建议剔除','补标后保留'] or not isinstance(v.get('note'),str) or len(v['note'])>4000:raise ValueError('Invalid discussion decision or note')
     result={'revision':old['revision']+1,'items':items,'updatedAt':now()};atomic(p,encoded(result));return self.reply(result)
   if path=='/api/order-review':
    with LOCK:return self.reply(order_review.apply(BASE,data))
   if path=='/api/remove-dataset':
    with LOCK:
     result=dataset_removal.apply(BASE,data)
     MANIFEST.clear();MANIFEST.update(json.loads((DIST/'data/manifest.json').read_text()))
     NAMES.clear();NAMES.update(r['name'] for r in MANIFEST['files'])
     return self.reply(result)
   name=data.get('name');original(name)
   with LOCK:
    d=document(name)
    if data.get('revision')!=d['revision']:return self.reply({'error':'此图已在其他窗口更新，请刷新后继续，当前编辑尚未覆盖'},409)
    if path=='/api/save':
     # Save the exact durable draft only, so export and draft never diverge.
     for filename,content in artifacts(d).items():atomic(OUTPUT/filename,content)
     atomic(OUTPUT/'README.txt',README.encode());return self.reply({'path':str(OUTPUT),'name':name,'boxes':len(d['shapes']),'revision':d['revision']})
    if path!='/api/draft':return self.reply({'error':'接口不存在'},404)
    v=validated(name,data);v.update(revision=d['revision']+1,updatedAt=now());atomic(DRAFTS/(name+'.json'),encoded(v));return self.reply({'revision':v['revision'],'updatedAt':v['updatedAt']})
  except (ValueError,TypeError,KeyError,json.JSONDecodeError) as e:return self.reply({'error':str(e)},400)
  except Exception as e:print('ERROR',repr(e),flush=True);return self.reply({'error':'保存失败，草稿可能尚未写入，请重试并检查磁盘'},500)
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=8879);args=parser.parse_args()
 server=ThreadingHTTPServer(('127.0.0.1',args.port),Handler);print(f'Silk 标注工作台 http://127.0.0.1:{args.port}',flush=True);print('保存目录：'+str(OUTPUT),flush=True)
 try:server.serve_forever()
 except KeyboardInterrupt:server.server_close()
