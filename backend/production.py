"""Deployment configuration, request protection and merchant tracking proofs."""
import base64
import hashlib
import hmac
import json
import logging
import os
import secrets
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from contextlib import contextmanager
from fastapi import HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

log=logging.getLogger('kiaasa.requests')

def production(): return os.getenv('APP_ENV','development').lower()=='production'
def require_tracking_verification():
    return os.getenv('TRACKING_REQUIRE_VERIFICATION','true' if production() else 'false').lower() not in {'false','0','no'}
def secret():
    return os.getenv('SESSION_SECRET') or _development_secret
_development_secret=secrets.token_urlsafe(48)

def validate_configuration():
    if production():
        if len(os.getenv('SESSION_SECRET',''))<32 or os.getenv('SESSION_SECRET','').startswith(('replace-','change-me','your_')):
            raise RuntimeError('Production requires SESSION_SECRET with at least 32 characters.')
        if not os.getenv('ALLOWED_HOSTS','').strip() or '*' in os.getenv('ALLOWED_HOSTS',''):
            raise RuntimeError('Production requires explicit ALLOWED_HOSTS.')
        if '*' in os.getenv('ALLOWED_ORIGINS',''):
            raise RuntimeError('Wildcard ALLOWED_ORIGINS is not supported in production.')
        if not require_tracking_verification():
            raise RuntimeError('Customer tracking verification must remain enabled in production.')

def sign_token(payload, purpose='session'):
    body=base64.urlsafe_b64encode(json.dumps(payload,separators=(',',':')).encode()).decode().rstrip('=')
    key=secret() if purpose=='session' else os.getenv('TRACKING_VERIFICATION_SECRET','')
    if not key:raise ValueError('Tracking verification is not configured.')
    signature=hmac.new(key.encode(),(purpose+'.'+body).encode(),hashlib.sha256).hexdigest()
    return body+'.'+signature

def verify_token(token,purpose='session'):
    try:
        if len(token)>4096:return None
        body,signature=token.split('.')
        payload=json.loads(base64.urlsafe_b64decode(body+'='*(-len(body)%4)))
        if not hmac.compare_digest(sign_token(payload,purpose),token):return None
        if not isinstance(payload.get('exp'),(int,float)) or payload['exp']<=time.time():return None
        return payload
    except (ValueError,TypeError,AttributeError,UnicodeError):return None

def require_session(request, session_id):
    if not production():return
    proof=verify_token(request.headers.get('x-session-token',''))
    if not proof or proof.get('sid')!=session_id:
        raise HTTPException(status_code=401,detail='Your chat session expired. Start a new chat and try again.')

def tracking_allowed(reference,kind,session_id,token):
    if not require_tracking_verification():return True
    proof=verify_token(token or '', 'tracking')
    return bool(proof and proof.get('reference')==reference and proof.get('kind')==kind and proof.get('sid')==session_id)

class StateStore:
    """SQLite state shared across requests and preserved over process restarts."""
    def __init__(self,path):
        self.path=str(path);self.lock=threading.RLock();self.initialized=False
    @contextmanager
    def connect(self):
        Path(self.path).parent.mkdir(parents=True,exist_ok=True)
        connection=sqlite3.connect(self.path,timeout=15)
        connection.execute('PRAGMA journal_mode=WAL')
        if not self.initialized:
            connection.executescript('CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, data TEXT NOT NULL, expires REAL NOT NULL); CREATE TABLE IF NOT EXISTS limits (key TEXT PRIMARY KEY, count INTEGER NOT NULL, expires REAL NOT NULL);')
            self.initialized=True
        try:
            with connection:
                yield connection
        finally:
            connection.close()
    def load(self,sid):
        with self.lock,self.connect() as db:
            db.execute('DELETE FROM sessions WHERE expires <= ?',(time.time(),))
            row=db.execute('SELECT data FROM sessions WHERE id=?',(sid,)).fetchone()
        return json.loads(row[0]) if row else None
    def save(self,sid,value):
        with self.lock,self.connect() as db:
            db.execute('DELETE FROM sessions WHERE expires <= ?',(time.time(),))
            db.execute('INSERT OR REPLACE INTO sessions VALUES (?,?,?)',(sid,json.dumps(value),time.time()+2700))
            db.execute('DELETE FROM sessions WHERE id IN (SELECT id FROM sessions ORDER BY expires DESC LIMIT -1 OFFSET 10000)')
    def delete(self,sid):
        with self.lock,self.connect() as db:db.execute('DELETE FROM sessions WHERE id=?',(sid,))
    def permit(self,key,limit,window=60):
        now=time.time();bucket=int(now//window);key=key+':'+str(bucket)
        with self.lock,self.connect() as db:
            db.execute('DELETE FROM limits WHERE expires <= ?',(now,))
            db.execute('INSERT INTO limits VALUES (?,1,?) ON CONFLICT(key) DO UPDATE SET count=count+1',(key,(bucket+1)*window))
            count=db.execute('SELECT count FROM limits WHERE key=?',(key,)).fetchone()[0]
        return count<=limit,max(1,int((bucket+1)*window-now)+1)

state_store=StateStore(os.getenv('STATE_DB_PATH',str(Path(__file__).resolve().parent/'data/runtime/state.sqlite3')))

class RequestProtection(BaseHTTPMiddleware):
    async def dispatch(self,request,call_next):
        request_id=uuid.uuid4().hex
        start=time.monotonic()
        if request.headers.get('content-length','0').isdigit() and int(request.headers.get('content-length','0'))>16384:
            return JSONResponse({'detail':'Request is too large.'},status_code=413)
        path=request.url.path
        if request.method not in {'GET','HEAD','OPTIONS'}:
            chunks=[];size=0
            async for chunk in request.stream():
                size+=len(chunk)
                if size>16384:return JSONResponse({'detail':'Request is too large.'},status_code=413)
                chunks.append(chunk)
            request._body=b''.join(chunks)
        if request.method not in {'HEAD','OPTIONS'} and ('/chat' in path or '/tracking' in path or path.endswith('/session')):
            address=request.client.host if request.client else 'unknown'
            hashed=hmac.new(secret().encode(),address.encode(),hashlib.sha256).hexdigest()
            limit=10 if path.endswith('/session') else 12 if '/tracking' in path else 30
            from starlette.concurrency import run_in_threadpool
            permitted,retry=await run_in_threadpool(state_store.permit,hashed+':'+('session' if path.endswith('/session') else 'tracking' if '/tracking' in path else 'chat'),limit)
            if not permitted:
                return JSONResponse({'detail':'Too many requests. Please wait and try again.'},status_code=429,headers={'Retry-After':str(retry),'X-Request-ID':request_id,'Cache-Control':'no-store'})
        try:
            response=await call_next(request)
        except Exception as error:
            log.error('request_failed id=%s method=%s type=%s',request_id,request.method,type(error).__name__)
            response=JSONResponse({'detail':'Something went wrong. Please try again.','request_id':request_id},status_code=500)
        response.headers['X-Request-ID']=request_id
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['Referrer-Policy']='strict-origin-when-cross-origin'
        response.headers['Cache-Control']='no-store'
        if production():response.headers['Strict-Transport-Security']='max-age=31536000'
        log.info('request id=%s method=%s status=%d duration_ms=%d',request_id,request.method,response.status_code,int((time.monotonic()-start)*1000))
        return response
