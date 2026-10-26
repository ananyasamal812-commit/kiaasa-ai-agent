"""Kiaasa shopping API with grounded recommendations and Shiprocket tracking."""
import json
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from fastapi import Request
from starlette.middleware.trustedhost import TrustedHostMiddleware
import threading
import secrets


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / '.env')

from production import (production, validate_configuration, state_store, sign_token,
                        require_session, tracking_allowed, require_tracking_verification, RequestProtection)

from catalogue_sync import catalogue_sync
from catalogue_overrides import apply_catalogue_overrides
from openai_assistant import openai_assistant
from groq_assistant import groq_assistant
from collections_menu import COLLECTION_INTROS, browse_collection
from order_tracking import handle_order_tracking, tracking_sessions
from shopping_assistant import (WELCOME, fresh_profile, is_greeting, update_profile,
    search, decorate, shopping_response, reply, service_answer)

PRODUCT_FILE = str(BASE_DIR / 'data/products.json')

@asynccontextmanager
async def lifespan(app):
    validate_configuration()
    catalogue_sync.start()
    try:
        yield
    finally:
        catalogue_sync.stop()

app = FastAPI(title='Kiaasa AI Shopping Agent', description='Catalogue-grounded shopping and order tracking', lifespan=lifespan, docs_url=None if production() else '/docs', redoc_url=None if production() else '/redoc', openapi_url=None if production() else '/openapi.json')
origins=[x.strip() for x in os.getenv('ALLOWED_ORIGINS','' if production() else 'http://localhost:5500,http://127.0.0.1:5500').split(',') if x.strip()]
app.add_middleware(RequestProtection)
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=False,
                   allow_methods=['GET','POST','DELETE','OPTIONS'],
                   allow_headers=['Content-Type','X-Session-Token','X-Tracking-Token'],
                   expose_headers=['Retry-After','X-Request-ID'])
if os.getenv('ALLOWED_HOSTS'):
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=[x.strip() for x in os.environ['ALLOWED_HOSTS'].split(',')])


class ChatRequest(BaseModel):
    message: str = Field(min_length=1,max_length=2000)
    session_id: str = Field(min_length=1,max_length=160,pattern=r'^[A-Za-z0-9_-]+$')
    action: str | None = Field(default=None,max_length=30)
    tracking_token: str | None = Field(default=None,max_length=4096)

def load_products():
    try:
        return apply_catalogue_overrides(json.loads(Path(PRODUCT_FILE).read_text(encoding='utf-8')))
    except (OSError, ValueError):
        return []

PRODUCTS = load_products()
_catalogue_mtime = Path(PRODUCT_FILE).stat().st_mtime_ns if Path(PRODUCT_FILE).exists() else None
customer_profiles = {}
chat_sessions = {}
session_last_seen = {}

def refresh_catalogue():
    global PRODUCTS, _catalogue_mtime
    try:
        current = Path(PRODUCT_FILE).stat().st_mtime_ns
        if current != _catalogue_mtime:
            updated = json.loads(Path(PRODUCT_FILE).read_text(encoding='utf-8'))
            if isinstance(updated, list):
                PRODUCTS, _catalogue_mtime = apply_catalogue_overrides(updated), current
    except (OSError, ValueError):
        pass  # Keep the last valid snapshot if a refresh is interrupted.

def reset_session(session_id):
    customer_profiles.pop(session_id, None)
    chat_sessions.pop(session_id, None)
    tracking_sessions.pop(session_id, None)
    session_last_seen.pop(session_id, None)
    state_store.delete(session_id)

def update_customer_profile(session_id, message):
    profile = customer_profiles.setdefault(session_id, fresh_profile())
    update_profile(profile, message, chat_sessions.get(session_id, {}).get('awaiting'))
    return profile

def search_products(profile, limit=5):
    return search(PRODUCTS, profile, limit=limit)[0]

@app.get('/')
def home():
    refresh_catalogue()
    return {'status': 'Kiaasa AI Agent is running', 'products_loaded': len(PRODUCTS)}

@app.get('/catalogue/status')
def catalogue_status():
    refresh_catalogue()
    return {**catalogue_sync.status(), 'products_loaded': len(PRODUCTS)}

def language_assistant():
    provider = os.getenv('LLM_PROVIDER', 'groq').strip().lower()
    return {'groq':groq_assistant, 'openai':openai_assistant}.get(provider)

@app.get('/llm/status')
def llm_status():
    assistant = language_assistant()
    return assistant.status() if assistant else {'provider':'local', 'enabled':False, 'configured':False, 'model':None}

_session_locks=[threading.RLock() for _ in range(64)]

@app.post('/session')
def create_session():
    sid=secrets.token_urlsafe(32)
    return {'session_id':sid,'session_token':sign_token({'sid':sid,'exp':time.time()+86400})}

@app.get('/health/live')
def health_live():
    return {'status':'ok'}

@app.get('/health/ready')
def health_ready():
    refresh_catalogue()
    if not PRODUCTS:raise HTTPException(status_code=503,detail='Catalogue not ready.')
    return {'status':'ready','products_loaded':len(PRODUCTS)}

@app.post('/chat')
def chat(request: ChatRequest, http_request: Request = None):
    if http_request is not None:require_session(http_request,request.session_id)
    with _session_locks[hash(request.session_id)%len(_session_locks)]:
        stored=state_store.load(request.session_id)
        if stored and request.session_id not in customer_profiles:
            customer_profiles[request.session_id]=stored.get('profile',fresh_profile())
            chat_sessions[request.session_id]=stored.get('context',{})
            if stored.get('tracking'):tracking_sessions[request.session_id]=stored['tracking']
            session_last_seen[request.session_id]=time.monotonic()
        result=chat_logic(request)
        state_store.save(request.session_id,{'profile':customer_profiles.get(request.session_id,fresh_profile()),
            'context':chat_sessions.get(request.session_id,{}),'tracking':tracking_sessions.get(request.session_id)})
        return result

def chat_logic(request: ChatRequest):
    message, session_id = request.message.strip(), request.session_id.strip()
    if not message:
        raise HTTPException(status_code=400, detail='Message cannot be empty.')
    if not session_id:
        raise HTTPException(status_code=400, detail='Session ID is required.')
    if len(message)>2000 or len(session_id)>160:
        raise HTTPException(status_code=400, detail='Please send a shorter message.')
    refresh_catalogue()
    now = time.monotonic()
    for key, last_seen in list(session_last_seen.items()):
        if now-last_seen>45*60:
            reset_session(key)
    if len(session_last_seen)>=1000 and session_id not in session_last_seen:
        reset_session(min(session_last_seen, key=session_last_seen.get))
    if request.action and request.action not in {*COLLECTION_INTROS,'reset'}:
        raise HTTPException(status_code=400,detail='Unknown chat action.')
    if request.action=='reset' or is_greeting(message):
        reset_session(session_id)
        session_last_seen[session_id]=now
        profile=customer_profiles.setdefault(session_id,fresh_profile())
        return reply(WELCOME,profile,'greeting',show_menu=True)
    session_last_seen[session_id]=now
    # Explicit menu clicks start a new collection. Typed replies retain preferences.
    if request.action in COLLECTION_INTROS:
        reset_session(session_id)
        session_last_seen[session_id]=now
        profile=customer_profiles.setdefault(session_id,fresh_profile())
        profile['collection']=request.action
        result=browse_collection(PRODUCTS,request.action)
        result['products']=[decorate(p,profile) for p in result['products']]
        result['profile']=profile
        context=chat_sessions.setdefault(session_id,{})
        context['last_products']=result['products'][:5]
        context['awaiting']='budget'
        result['reply']+=' What budget would you like to stay within?'
        return result
    tracking=handle_order_tracking(session_id,message,verification_token=request.tracking_token)
    if tracking is not None:
        return tracking
    profile=customer_profiles.setdefault(session_id,fresh_profile())
    context=chat_sessions.setdefault(session_id,{})
    service = service_answer(message, profile)
    if service is not None:
        return service
    assistant = language_assistant()
    interpreted = assistant.interpret(message, profile, context) if assistant else None
    result = shopping_response(PRODUCTS, profile, context, interpreted or message,
                               original_message=message if interpreted else None)
    result['language_model'] = assistant.status()['provider'] if interpreted else 'local'
    return result

@app.delete('/chat/{session_id}')
def clear_chat(session_id: str, http_request: Request = None):
    if http_request is not None:require_session(http_request,session_id)
    reset_session(session_id)
    return {'message': 'Conversation cleared.'}


@app.get('/tracking/{awb}')
def tracking_update(awb: str, http_request: Request):
    import re
    from shiprocket_client import shiprocket, ShiprocketError
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{2,39}', awb):
        raise HTTPException(status_code=400, detail='Invalid tracking number.')
    sid=http_request.headers.get('x-session-id','')
    if require_tracking_verification():
        from production import verify_token
        proof=verify_token(http_request.headers.get('x-session-token',''))
        sid=proof.get('sid','') if proof else ''
        if not sid or not tracking_allowed(awb,'awb',sid,http_request.headers.get('x-tracking-token','')):
            raise HTTPException(status_code=403,detail='Verify order ownership on Kiaasa before viewing tracking updates.')
    try:
        shipments = shiprocket.track(awb, kind='awb')
    except ShiprocketError as error:
        status = 404 if error.code in {'not_found', 'invalid_reference'} else 503
        raise HTTPException(status_code=status, detail='No shipment updates found.' if status == 404 else 'Tracking updates are temporarily unavailable. Please try again.') from None
    from fastapi.responses import JSONResponse
    return JSONResponse({'tracking': shipments}, headers={'Cache-Control': 'no-store'})
