import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from liuyao_app import people_assistant as a
from liuyao_app.zhiren_v09_store import ZhirenV09Data

class PeopleAssistantTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'people.db';self.owner='owner';self.ui=ZhirenV09Data(self.path)
    def tearDown(self):self.tmp.cleanup()
    def test_extract_requires_evidence_and_keeps_conversation(self):
        response={'parsed_json':{'answer':'请确认','people':[{'subject':'contact','label':'王先生','fields':[
          {'field':'city','value':'成都','evidence':'在成都做汽车测试'},
          {'field':'company','value':'虚构公司','evidence':'在成都做汽车测试'},
          {'field':'birthday','value':'05-06','evidence':'生日是5月6日'}],
          'records':[{'kind':'agreement','content':'下周联系','evidence':'约好下周联系','date':''}], 'missing':[]} ]}}
        payload={'provider':'deepseek','model':'test','text':'生日是5月6日，约好下周联系','history':[{'text':'王先生在成都做汽车测试','result':{'action':'people_edit'}}]}
        with patch.object(a,'generate_json',return_value=response) as model:
            result=a.extract(payload)
        self.assertEqual([x['field'] for x in result['people'][0]['fields']],['city','birthday'])
        self.assertEqual(result['people'][0]['records'][0]['kind'],'agreement')
        self.assertEqual(len(model.call_args.args[3]['messages']),2)
    def test_apply_atomic_idempotent_and_revision_conflict(self):
        change={'target':'new','name':'王先生','fields':[{'field':'city','value':'成都','operation':'replace'},
          {'field':'birthday','value':'05-06','operation':'replace'}],
          'records':[{'kind':'agreement','content':'下周联系','date':'','source':'约好下周联系'}]}
        self.assertEqual(a.apply(self.path,self.owner,{'revision':0,'changes':[change]},'first')['revision'],1)
        self.assertTrue(a.apply(self.path,self.owner,{'revision':0,'changes':[change]},'first')['saved'])
        state=self.ui.load(self.owner)['state'];self.assertEqual(len(state['people']),1)
        p=state['people'][0];self.assertEqual(p['birthdayMD'],'05-06');self.assertEqual(state['events'][0]['people'],[p['id']])
        with self.assertRaises(ValueError):a.apply(self.path,self.owner,{'revision':0,'changes':[change]},'other')
        bad={'target':p['id'],'name':'','fields':[{'field':'birthday','value':'02-31','operation':'replace'}],'records':[]}
        with self.assertRaises(ValueError):a.apply(self.path,self.owner,{'revision':1,'changes':[bad]},'bad')
        self.assertEqual(self.ui.load(self.owner)['revision'],1)
    def test_append_and_keep_existing(self):
        initial={'target':'new','name':'李先生','fields':[{'field':'skills','value':'测试','operation':'append'}],'records':[]}
        a.apply(self.path,self.owner,{'revision':0,'changes':[initial]},'a')
        p=self.ui.load(self.owner)['state']['people'][0]
        update={'target':p['id'],'name':'','fields':[{'field':'skills','value':'Python','operation':'append'}, {'field':'name','value':'其他名字','operation':'keep'}],'records':[]}
        a.apply(self.path,self.owner,{'revision':1,'changes':[update]},'b')
        p=self.ui.load(self.owner)['state']['people'][0]
        self.assertEqual(p['skills'],['测试','Python']);self.assertEqual(p['name'],'李先生')
    def test_experience_extraction_and_non_destructive_append(self):
        text='我在甲公司做了三年测试，大学在成都学习。'
        raw={'parsed_json':{'people':[{'subject':'self','fields':[{'field':'career','value':'在甲公司做了三年测试','evidence':'我在甲公司做了三年测试'},{'field':'education','value':'大学在成都学习','evidence':'大学在成都学习'}]}]}}
        with patch.object(a,'generate_json',return_value=raw):
            result=a.extract({'provider':'deepseek','text':text})
        self.assertEqual([f['field'] for f in result['people'][0]['fields']],['career','education'])
        change={'target':'self','name':'','fields':[{'field':'career','value':'原有经历','operation':'replace'}],'records':[]}
        a.apply(self.path,self.owner,{'revision':0,'changes':[change]},'career1')
        change['fields']=[{'field':'career','value':'新增经历','operation':'append'},{'field':'education','value':'大学在成都学习','operation':'replace'}]
        a.apply(self.path,self.owner,{'revision':1,'changes':[change]},'career2')
        self.assertEqual(self.ui.load(self.owner)['state']['self']['career'],'原有经历\n\n新增经历')
        self.assertEqual(self.ui.load(self.owner)['state']['self']['education'],'大学在成都学习')
        change['fields']=[{'field':'career','value':'x'*600,'operation':'append'}]
        for revision in (2,3,4,5,6):
            if revision==6:
                with self.assertRaises(ValueError):a.apply(self.path,self.owner,{'revision':revision,'changes':[change]},'overflow')
            else:a.apply(self.path,self.owner,{'revision':revision,'changes':[change]},'long'+str(revision))
        self.assertEqual(self.ui.load(self.owner)['revision'],6)
if __name__=='__main__':unittest.main()
