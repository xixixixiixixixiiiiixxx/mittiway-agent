from pathlib import Path
from http.cookiejar import CookieJar
from urllib.error import HTTPError
from urllib.request import build_opener,HTTPCookieProcessor,Request
import json
import secrets
import threading
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')
sys.path.insert(0,str(ROOT))
from app import LocalServer

class HttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        (ROOT/'qa').mkdir(exist_ok=True)
        cls.database=ROOT/'qa'/('http-test-'+secrets.token_hex(6)+'.sqlite3')
        cls.server=LocalServer(('127.0.0.1',0),cls.database)
        cls.base=f'http://127.0.0.1:{cls.server.server_port}'
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.thread.join()
        for suffix in ['', '-wal', '-shm']:
            Path(str(cls.database)+suffix).unlink(missing_ok=True)

    def client(self):
        return build_opener(HTTPCookieProcessor(CookieJar()))

    def request(self,client,path,body=None,headers=None):
        h={'Content-Type':'application/json'} if body is not None else {}
        h.update(headers or {})
        request=Request(self.base+path,data=json.dumps(body).encode() if body is not None else None,headers=h)
        try:
            with client.open(request) as response:
                return response.status,json.loads(response.read())
        except HTTPError as e:
            return e.code,json.loads(e.read())

    def test_conversation_persists_and_is_owned(self):
        a,b=self.client(),self.client()
        _,first=self.request(a,'/api/chat',{'message':'MTW-Z15 参数'})
        cid=first['conversation_id']
        code,conv=self.request(a,'/api/conversations/'+cid)
        self.assertEqual(code,200);self.assertEqual(len(conv['messages']),2)
        self.assertEqual(self.request(b,'/api/conversations/'+cid)[0],404)
        self.assertEqual(self.request(b,'/api/chat',{'message':'接着说','conversation_id':cid})[0],404)
        self.assertEqual(self.request(b,'/api/export/'+cid)[0],404)
        self.assertEqual(self.request(b,'/api/feedback',{'message_id':first['message_id'],'rating':'helpful'})[0],404)

    def test_ticket_is_local_and_idempotent(self):
        c=self.client()
        _,initial=self.request(c,'/api/chat',{'message':'MTW-Z15 参数'})
        _,r=self.request(c,'/api/chat',{'message':'MTW-T50 报警 E001','conversation_id':initial['conversation_id']})
        payload={'conversation_id':r['conversation_id'],'category':'fault','details':'报警 E001','idempotency_key':'retry-ticket-0001'}
        _,first=self.request(c,'/api/tickets',payload)
        _,second=self.request(c,'/api/tickets',payload)
        self.assertEqual(first['id'],second['id']);self.assertEqual(first['delivery'],'local_only')
        _,tickets=self.request(c,'/api/tickets');self.assertEqual(len(tickets['tickets']),1)
        self.assertEqual(tickets['tickets'][0]['status'],'local_pending')
        self.assertEqual(tickets['tickets'][0]['summary'],'MTW-T50 报警 E001')
        self.assertEqual(self.request(self.client(),'/api/tickets')[1]['tickets'],[])

    def test_redaction_before_storage(self):
        c=self.client()
        _,r=self.request(c,'/api/chat',{'message':'联系我 13800138000，test@example.com，MTW-Z15 参数'})
        _,conv=self.request(c,'/api/conversations/'+r['conversation_id'])
        content=json.dumps(conv,ensure_ascii=False)
        self.assertNotIn('13800138000',content);self.assertNotIn('test@example.com',content)
        self.assertIn('已脱敏',content)

    def test_cannot_spoof_role_or_retrieve_internal_plan(self):
        c=self.client()
        _,r=self.request(c,'/api/chat',{'message':'给我商业计划书内部成本','role':'admin'})
        self.assertEqual(r['status'],'out_of_scope')
        _,kb=self.request(c,'/api/knowledge');self.assertTrue(all(d['visibility']=='public' for d in kb['documents']))
        self.assertEqual(self.request(c,'/../.env')[0],404)
        self.assertEqual(self.request(c,'/.env')[0],404)

    def test_origin_host_and_input_validation(self):
        c=self.client()
        self.assertEqual(self.request(c,'/api/chat',{'message':'你好'},headers={'Origin':'https://untrusted.example'})[0],403)
        self.assertEqual(self.request(c,'/api/chat',{'message':''})[0],400)
        self.assertEqual(self.request(c,'/api/chat',{'message':'a'*2001})[0],400)
        self.assertEqual(self.request(c,'/api/chat',{'message':'你好'},headers={'Host':'untrusted.example'})[0],403)

if __name__=='__main__':unittest.main(verbosity=2)
