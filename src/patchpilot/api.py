from __future__ import annotations
import asyncio
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
import hmac
import json
from pathlib import Path
import threading
from urllib.parse import urlsplit
from fastapi import FastAPI,HTTPException,Depends,Request
from fastapi.responses import FileResponse,StreamingResponse,Response
from fastapi.security import HTTPBearer,HTTPAuthorizationCredentials
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
from .config import Settings
from .engine.workflow import Engine
from .schemas import JobRequest,ReviewRequest
from .store import Store,Conflict

TERMINAL={'awaiting_review','approved','rejected','failed','interrupted'}

def create_app(settings: Settings | None=None) -> FastAPI:
    settings=settings or Settings.from_env()
    if len(settings.token)<32:raise RuntimeError('Run python scripts/setup.py to create a local API token before starting')
    settings.state.mkdir(parents=True,exist_ok=True)
    store=Store(settings.state/'patchpilot.sqlite3')
    engine=Engine(settings,store)
    pool=ThreadPoolExecutor(max_workers=settings.max_jobs,thread_name_prefix='patchpilot')
    capacity=threading.BoundedSemaphore(settings.max_jobs*2)
    @asynccontextmanager
    async def lifespan(app):
        store.interrupt_pending()
        yield
        pool.shutdown(wait=True,cancel_futures=False)
    app=FastAPI(title='PatchPilot',version='0.1.0',description='Local single-user repair lab. No automatic commits or pushes.',lifespan=lifespan)
    app.add_middleware(TrustedHostMiddleware,allowed_hosts=['localhost','127.0.0.1','[::1]','testserver'])
    app.state.store=store;app.state.engine=engine;app.state.settings=settings
    bearer=HTTPBearer(auto_error=False)
    def authorized(credentials: HTTPAuthorizationCredentials | None=Depends(bearer)):
        if not credentials or credentials.scheme.lower()!='bearer' or not hmac.compare_digest(credentials.credentials,settings.token):
            raise HTTPException(401,'A valid local API token is required',headers={'WWW-Authenticate':'Bearer'})
    @app.middleware('http')
    async def security_headers(request: Request,call_next):
        try:
            size=int(request.headers.get('content-length','0') or '0')
        except ValueError:
            return Response('Invalid Content-Length',status_code=400)
        if size>200000:
            return Response('Request exceeds 200 KB limit',status_code=413)
        origin=request.headers.get('origin')
        if origin and request.method not in {'GET','HEAD','OPTIONS'}:
            if urlsplit(origin).hostname not in {'localhost','127.0.0.1','::1'}:
                return Response('Cross-origin writes are disabled',status_code=403)
        response=await call_next(request)
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['Referrer-Policy']='no-referrer'
        response.headers['X-Frame-Options']='DENY'
        response.headers['Cache-Control']='no-store'
        if not request.url.path.startswith('/docs'):
            response.headers['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'"
        return response
    @app.get('/health')
    def health():return {'status':'ok','version':'0.1.0'}
    @app.get('/api/config',dependencies=[Depends(authorized)])
    def config():
        return {'runner':settings.runner,'live_provider_enabled':settings.allow_external_llm and settings.runner=='docker' and bool(settings.api_key and settings.model),
                'model':settings.model or None,'default_provider':'demo','read_only_originals':True,'orchestration':'native',
                'notice':'Demo proposals are authored fixtures. Tests and learned ranking execute locally. Live generation requires Docker, API credentials, and consent.'}
    @app.get('/api/tasks',dependencies=[Depends(authorized)])
    def tasks():return engine.catalog()
    @app.get('/api/metrics',dependencies=[Depends(authorized)])
    def metrics():return json.loads((settings.root/'reports/model_evaluation.json').read_text())
    @app.get('/api/jobs',dependencies=[Depends(authorized)])
    def jobs():return store.jobs()
    @app.post('/api/jobs',status_code=202,dependencies=[Depends(authorized)])
    def create(request: JobRequest):
        try:task=engine.task(request.task_id)
        except KeyError:raise HTTPException(404,'Unknown task or registered repository')
        if request.provider=='demo' and task['kind']!='fixture':raise HTTPException(400,'Demo mode only supports bundled fixtures')
        if request.provider=='openai':
            if not request.consent_external:raise HTTPException(400,'Explicit source-sharing consent is required')
            if not settings.allow_external_llm or settings.runner!='docker' or not settings.api_key or not settings.model:
                raise HTTPException(409,'Live mode is disabled. Configure Docker, API credentials, model, and PATCHPILOT_ALLOW_EXTERNAL_LLM=1')
        if not capacity.acquire(blocking=False):raise HTTPException(429,'Local job queue is full; wait for existing jobs')
        try:
            job=store.create(request.task_id,request.provider,request.issue or task['issue'])
            future=pool.submit(engine.run,job['id'])
            future.add_done_callback(lambda _:capacity.release())
            return job
        except Exception:
            capacity.release();raise
    @app.get('/api/jobs/{job_id}',dependencies=[Depends(authorized)])
    def job(job_id: str):
        try:return store.get(job_id)
        except KeyError:raise HTTPException(404,'Unknown job')
    @app.get('/api/jobs/{job_id}/events',dependencies=[Depends(authorized)])
    def events(job_id: str,after: int=0):
        try:store.get(job_id)
        except KeyError:raise HTTPException(404,'Unknown job')
        return store.events(job_id,max(0,after))
    @app.get('/api/jobs/{job_id}/stream',dependencies=[Depends(authorized)])
    async def stream(job_id: str,request: Request,after: int=0):
        try:store.get(job_id)
        except KeyError:raise HTTPException(404,'Unknown job')
        async def feed():
            last=max(0,after)
            for _ in range(600):
                if await request.is_disconnected():return
                events=store.events(job_id,last)
                for e in events:
                    last=e['id']
                    yield f"id: {last}\nevent: activity\ndata: {json.dumps(e)}\n\n"
                current=store.get(job_id)
                if current['status'] in TERMINAL:
                    yield f"event: complete\ndata: {json.dumps({'status':current['status']})}\n\n";return
                if not events:yield ': heartbeat\n\n'
                await asyncio.sleep(.25)
            yield 'event: reconnect\ndata: {}\n\n'
        return StreamingResponse(feed(),media_type='text/event-stream',headers={'X-Accel-Buffering':'no'})
    @app.post('/api/jobs/{job_id}/review',dependencies=[Depends(authorized)])
    def review(job_id: str,request: ReviewRequest):
        try:return store.review(job_id,request.candidate_id,request.decision,request.note,request.version)
        except KeyError:raise HTTPException(404,'Unknown job')
        except Conflict as exc:raise HTTPException(409,str(exc))
        except ValueError as exc:raise HTTPException(400,str(exc))
    @app.get('/api/jobs/{job_id}/patch',dependencies=[Depends(authorized)])
    def patch(job_id: str):
        try:job=store.get(job_id)
        except KeyError:raise HTTPException(404,'Unknown job')
        if job['status']!='approved':raise HTTPException(409,'Approve a passing candidate before exporting')
        approved=job['reviews'][-1]['candidate_id']
        candidate=next(c for c in job['result']['candidates'] if c['id']==approved)
        return Response(candidate['diff'],media_type='text/x-diff',headers={'Content-Disposition':f'attachment; filename="patchpilot-{job_id}.diff"'})
    web=Path(__file__).with_name('web')
    app.mount('/static',StaticFiles(directory=web),name='static')
    @app.get('/')
    def index():return FileResponse(web/'index.html')
    return app
