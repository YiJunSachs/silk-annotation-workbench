import unittest,importlib.util,sys,tempfile,threading,json,urllib.request,urllib.error,zipfile,io,xml.etree.ElementTree as ET,base64
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];spec=importlib.util.spec_from_file_location('silk_server',ROOT/'server.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class EditorTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.temp=tempfile.TemporaryDirectory();m.DRAFTS=Path(cls.temp.name)/'drafts';m.OUTPUT=Path(cls.temp.name)/'output';cls.server=m.ThreadingHTTPServer(('127.0.0.1',0),m.Handler);cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start();cls.url='http://127.0.0.1:'+str(cls.server.server_port)
 @classmethod
 def tearDownClass(cls):cls.server.shutdown();cls.server.server_close();cls.temp.cleanup()
 def request(self,path,data=None,headers=None):
  body=None if data is None else json.dumps(data,ensure_ascii=False).encode();h={'X-Silk-Editor':'1','Content-Type':'application/json'};h.update(headers or {})
  req=urllib.request.Request(self.url+path,data=body,headers=h)
  try:
   with urllib.request.urlopen(req) as r:return r.status,r.read()
  except urllib.error.HTTPError as e:return e.code,e.read()
 def test_01_all_sources_export_lossless(self):
  for row in m.MANIFEST['files']:
   d=m.original(row['name']);parts=m.artifacts(d);lm=json.loads(parts['annotations-json/'+d['name']+'.json']);gt=parts['gt-label/'+d['name']+'.txt'].decode();co=parts['coordinate/'+d['name']+'.txt'].decode().splitlines();xml=ET.fromstring(parts['annotations-xml/'+d['name']+'.xml']);sp=json.loads(parts['gt-index/'+d['name']+'.json'])
   self.assertEqual(len(lm['shapes']),len(co));self.assertEqual(len(xml.findall('object')),len(co));self.assertNotIn('\n',gt);self.assertEqual(gt,''.join(x['label'] for x in d['shapes']))
   for i,s in enumerate(d['shapes']):self.assertEqual(list(map(float,co[i].split(','))),s['box']);self.assertEqual(gt[sp['spans'][i]['start']:sp['spans'][i]['end']],s['label'])
 def test_02_edit_persist_save_and_export(self):
  n='1-125';d=m.original(n);data={'name':n,'revision':0,'shapes':d['shapes'],'resolved':[],'reviewed':False};data['shapes'][0]['label']='測□𠀀';data['shapes'][0]['box']=[.2,.4,10.7,20.3]
  status,b=self.request('/api/draft',data);self.assertEqual(status,200,b);rev=json.loads(b)['revision'];self.assertEqual(m.document(n)['shapes'][0]['label'],'測□𠀀')
  status,b=self.request('/api/draft',data);self.assertEqual(status,409)
  status,b=self.request('/api/save',{'name':n,'revision':rev});self.assertEqual(status,200,b);gt=(m.OUTPUT/'gt-label'/f'{n}.txt').read_text();self.assertTrue(gt.startswith('測□𠀀'));self.assertNotIn('\n',gt)
  status,b=self.request('/api/export?scope='+n+'&format=zip');self.assertEqual(status,200);z=zipfile.ZipFile(io.BytesIO(b));self.assertEqual(z.read('gt-label/'+n+'.txt').decode(),gt);self.assertIn('intact-img/'+n+'.png',z.namelist());obj=ET.fromstring(z.read('annotations-xml/'+n+'.xml')).find('object');self.assertEqual([obj.findtext('bndbox/'+k) for k in ['xmin','ymin','xmax','ymax']],['1','1','11','21'])
  status,b=self.request('/api/export?scope='+n+'&format=json');lm=json.loads(b);self.assertEqual(base64.b64decode(lm['imageData']),(m.DIST/'images'/f'{n}.png').read_bytes())
 def test_03_invalid_input_and_cross_site_rejected(self):
  d=m.original('1-32');bad={'name':d['name'],'revision':0,'shapes':d['shapes'],'reviewed':False};bad['shapes'][0]['box']=[-1,0,2,3];status,b=self.request('/api/draft',bad);self.assertEqual(status,400);self.assertFalse((m.DRAFTS/'1-32.json').exists())
  status,b=self.request('/api/draft',bad,{'Origin':'https://evil.example'});self.assertEqual(status,403)
  status,b=self.request('/api/doc/../../server.py');self.assertEqual(status,400)
 def test_04_discussion_roundtrip(self):
  status,b=self.request('/api/discussion',{'revision':0,'items':{'1-230':{'decision':'补标后保留','note':'测试备注'}}});self.assertEqual(status,200,b)
  status,b=self.request('/api/discussion');self.assertEqual(json.loads(b)['items']['1-230']['note'],'测试备注')
  status,b=self.request('/api/discussion',{'revision':1,'items':{'wrong':{'decision':'建议保留','note':''}}});self.assertEqual(status,400)
if __name__=='__main__':unittest.main()
