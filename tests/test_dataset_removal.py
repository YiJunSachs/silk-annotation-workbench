import unittest,tempfile,sys,json
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import dataset_removal as m
class RemovalTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.base=self.root/'workbench';self.b=self.root/'corpus';self.r=self.root/'backups';self.oldB,self.oldR=m.B,m.R;m.B=self.b;m.R=self.r
  self.w=self.base/'dist';q=self.b/'质量检查';rows=[]
  for n in ['1-50','1-52']:
   src=self.b/'source'/f'{n}.json';img=self.b/'source'/f'{n}.png';row={'name':n,'box_count':2,'annotation':str(src),'source_image':str(img),'order_adjustment':{'moved':2,'review_required':True}};rows.append(row)
   for p in [src,img,self.b/f'intact-img/{n}.png',self.b/f'coordinate/{n}.txt',self.b/f'gt-label/{n}.txt',self.w/f'data/{n}.json',self.w/f'all/data/{n}.json',self.w/f'order/data/{n}.json',self.base/f'草稿/{n}.json',self.base/f'保存结果/annotations-json/{n}.json']:self.write(p,b'fixture '+n.encode())
  for p,d in [(q/'逐文件检查明细.json',rows),(q/'提取来源与校验清单.json',rows),(q/'问题清单.json',rows),(q/'GT字符区间索引.json',{'files':rows}),(self.w/'all/index.json',{'images':2,'boxes':4,'files':[{'name':n,'boxes':2} for n in ['1-50','1-52']]}),(self.w/'order/index.json',{'boxes':4,'changed':2,'review':2,'files':[{'name':n,'boxes':2,'moved':2,'review':True} for n in ['1-50','1-52']]}),(self.w/'data/manifest.json',{'files':rows}),(self.w/'data/fragments.json',{'files':rows}),(self.base/'草稿/_order-review.json',{'revision':0,'items':{'1-50':{}}})]:self.write(p,m.enc(d))
 def write(self,p,b):p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b)
 def tearDown(self):m.B,m.R=self.oldB,self.oldR;self.temp.cleanup()
 def test_complete_and_backup(self):
  before={p:p.read_bytes() for root in [self.b,self.base] for p in root.rglob('*') if p.is_file()};pr=m.preview(self.base,'1-50');r=m.apply(self.base,dict(name='1-50',confirmName='1-50',token=pr['token']));self.assertEqual(r['remainingImages'],1)
  log=m.load(Path(r['logPath']));self.assertEqual(log['status'],'completed')
  for rec in log['files']:self.assertEqual(Path(rec['backup']).read_bytes(),before[Path(rec['path'])])
  for root in [self.base,self.b]:self.assertFalse(any(p.stem=='1-50' for p in root.rglob('*') if p.is_file()))
  self.assertTrue((self.b/'intact-img/1-52.png').exists());self.assertEqual(len(m.load(self.w/'data/manifest.json')['files']),1)
  with self.assertRaises(ValueError):m.preview(self.base,'1-50')
 def test_stale_and_traversal(self):
  with self.assertRaises(ValueError):m.preview(self.base,'../1-50')
  pr=m.preview(self.base,'1-50');p=self.b/'coordinate/1-50.txt';p.write_text('new edit')
  with self.assertRaises(ValueError):m.apply(self.base,dict(name='1-50',confirmName='1-50',token=pr['token']))
  self.assertEqual(p.read_text(),'new edit')
 def test_failed_write_rolls_back(self):
  before={p:p.read_bytes() for root in [self.b,self.base] for p in root.rglob('*') if p.is_file()};pr=m.preview(self.base,'1-50');real=m.atomic;failed=[False]
  def fail(p,b):
   if p==self.b/'质量检查/提取来源与校验清单.json' and not failed[0]:failed[0]=True;raise OSError('simulated disk error')
   return real(p,b)
  with patch.object(m,'atomic',fail):
   with self.assertRaises(OSError):m.apply(self.base,dict(name='1-50',confirmName='1-50',token=pr['token']))
  for p,b in before.items():self.assertEqual(p.read_bytes(),b)
 def test_backup_failure_does_not_remove(self):
  pr=m.preview(self.base,'1-50')
  with patch.object(m,'atomic',side_effect=OSError('backup unavailable')):
   with self.assertRaises(OSError):m.apply(self.base,dict(name='1-50',confirmName='1-50',token=pr['token']))
  self.assertTrue((self.b/'intact-img/1-50.png').exists())
if __name__=='__main__':unittest.main()
