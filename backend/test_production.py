import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
import main
import production
from production import StateStore, sign_token, verify_token, tracking_allowed, validate_configuration
from refresh_catalogue import allowed_source

class ProductionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.store=StateStore(Path(self.tmp.name)/'state.sqlite3')
        env=patch.dict(os.environ,{'APP_ENV':'production','ALLOWED_HOSTS':'testserver,localhost','ALLOWED_ORIGINS':'https://shop.example.test','SESSION_SECRET':'test-session-secret-'*3,'TRACKING_VERIFICATION_SECRET':'test-merchant-proof-'*3,'TRACKING_REQUIRE_VERIFICATION':'true','LLM_PROVIDER':'local'})
        env.start();self.addCleanup(env.stop)
        for module in [main,production]:
            p=patch.object(module,'state_store',self.store);p.start();self.addCleanup(p.stop)
        p=patch.object(main.catalogue_sync,'enabled',False);p.start();self.addCleanup(p.stop)
        self.client=TestClient(main.app);self.client.__enter__();self.addCleanup(self.client.__exit__,None,None,None)
    def session(self):
        r=self.client.post('/session');self.assertEqual(r.status_code,200)
        d=r.json();return d['session_id'],{'X-Session-Token':d['session_token']}
    def ask(self,sid,headers,message,**extra):
        return self.client.post('/chat',headers=headers,json={'session_id':sid,'message':message,**extra})
    def test_unsigned_and_cross_session_requests_are_rejected(self):
        sid,headers=self.session()
        self.assertEqual(self.ask(sid,{},'hi').status_code,401)
        self.assertEqual(self.ask('another',headers,'hi').status_code,401)
        self.assertEqual(self.ask(sid,headers,'hi').status_code,200)
        self.assertEqual(self.client.delete('/chat/'+sid).status_code,401)
    def test_preferences_survive_memory_loss_and_delete(self):
        sid,headers=self.session()
        first=self.ask(sid,headers,'festive under 1500').json()
        self.assertTrue(first['products'])
        for mapping in [main.customer_profiles,main.chat_sessions,main.tracking_sessions,main.session_last_seen]:mapping.pop(sid,None)
        second=self.ask(sid,headers,'show more').json()
        self.assertEqual(second['profile']['budget'],1500)
        self.assertEqual(second['profile']['occasion'],'festive')
        self.assertEqual(self.client.delete('/chat/'+sid,headers=headers).status_code,200)
        self.assertIsNone(self.store.load(sid))
    @patch('production.time.time',return_value=2000000000)
    def test_rate_limit_has_retry_header(self,clock):
        sid,headers=self.session()
        for _ in range(30):self.assertEqual(self.ask(sid,headers,'hi').status_code,200)
        r=self.ask(sid,headers,'hi');self.assertEqual(r.status_code,429)
        self.assertGreater(int(r.headers['Retry-After']),0)
    def test_large_body_invalid_action_and_headers(self):
        r=self.client.post('/chat',content=b'x'*17000)
        self.assertEqual(r.status_code,413)
        sid,headers=self.session()
        self.assertEqual(self.ask(sid,headers,'hi',action='invalid').status_code,400)
        r=self.ask(sid,headers,'hi')
        self.assertEqual(r.headers['Cache-Control'],'no-store')
        self.assertEqual(r.headers['X-Content-Type-Options'],'nosniff')
        self.assertIn('X-Request-ID',r.headers)
    def test_tracking_fails_closed_without_merchant_proof(self):
        sid,headers=self.session()
        with patch('order_tracking.shiprocket.track') as lookup:
            self.ask(sid,headers,'track my order')
            r=self.ask(sid,headers,'123456').json()
            self.assertEqual(r['tracking_state'],'verification_required')
            lookup.assert_not_called()
        r=self.client.get('/tracking/123456',headers=headers)
        self.assertEqual(r.status_code,403)
    def test_verified_tracking_only_accepts_exact_reference_and_session(self):
        sid,headers=self.session()
        token=sign_token({'sid':sid,'reference':'123456','kind':'order','exp':time.time()+60},'tracking')
        self.assertTrue(tracking_allowed('123456','order',sid,token))
        self.assertFalse(tracking_allowed('999999','order',sid,token))
        self.assertFalse(tracking_allowed('123456','order','other',token))
        with patch('order_tracking.shiprocket.track',return_value=[{'status':'In Transit','awb':'123456'}]) as lookup:
            r=self.ask(sid,headers,'order 123456',tracking_token=token)
            self.assertEqual(r.status_code,200,r.text)
            self.assertEqual(r.json().get('tracking_state'),'found',r.text);lookup.assert_called_once()
    def test_token_tampering_expiry_and_config(self):
        token=sign_token({'sid':'abc','exp':time.time()+60})
        self.assertIsNotNone(verify_token(token));self.assertIsNone(verify_token(token+'x'))
        self.assertIsNone(verify_token(sign_token({'sid':'abc','exp':time.time()-1})))
        with patch.dict(os.environ,{'SESSION_SECRET':''}):
            self.assertRaises(RuntimeError,validate_configuration)
        with patch.dict(os.environ,{'TRACKING_REQUIRE_VERIFICATION':'false'}):
            self.assertRaises(RuntimeError,validate_configuration)
    def test_source_validation_and_persistent_expiry(self):
        self.assertTrue(allowed_source('https://www.kiaasa.in/product/test'))
        for url in ['http://www.kiaasa.in/product/test','https://127.0.0.1/','https://www.kiaasa.in.evil.test/','https://user:password@www.kiaasa.in/']:
            self.assertFalse(allowed_source(url))
        self.store.save('a',{'profile':{'budget':1500}})
        self.assertEqual(StateStore(self.store.path).load('a')['profile']['budget'],1500)
        with patch('production.time.time',return_value=time.time()+2800):self.assertIsNone(self.store.load('a'))
    def test_mount_serves_frontend_and_health(self):
        import app as combined
        with TestClient(combined.app) as client:
            self.assertEqual(client.get('/api/health/ready').status_code,200)
            self.assertIn('Kiaasa',client.get('/').text)
            self.assertEqual(client.get('/.env').status_code,404)

if __name__=='__main__':unittest.main()
