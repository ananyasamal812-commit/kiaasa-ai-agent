"""Same-origin application entrypoint for a persistent production server."""
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'backend'))
from main import app as backend_app

@asynccontextmanager
async def lifespan(app):
    async with backend_app.router.lifespan_context(backend_app):
        yield

app=FastAPI(lifespan=lifespan,docs_url=None,redoc_url=None,openapi_url=None)
app.mount('/api',backend_app)
app.mount('/',StaticFiles(directory=ROOT/'frontend',html=True),name='frontend')
