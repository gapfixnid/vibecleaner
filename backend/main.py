import os
import sys
import logging
import argparse
import asyncio
import uvicorn
from contextlib import asynccontextmanager
from urllib.parse import urlparse

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Add backend directory to sys.path to ensure local imports resolve
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from modules.logging_config import configure_logging
from app.version import APP_NAME, __version__ as APP_VERSION

configure_logging()
logger = logging.getLogger(APP_NAME)

from routes.settings import router as settings_router
from routes.project import router as project_router
from routes.pages import router as pages_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Suppress harmless ConnectionResetError on Windows during shutdown.
    # When Tauri respawns the backend, active HTTP connections are forcibly
    # closed. Python's asyncio tries to shutdown already-closed sockets and
    # raises WinError 10054. This is cosmetic — the process is exiting anyway.
    if sys.platform == "win32":
        try:
            loop = asyncio.get_running_loop()
            def _silent_exception_handler(loop, context):
                message = context.get("message", "")
                exception = context.get("exception")
                exc_str = str(exception) if exception else ""
                if "ConnectionResetError" in message or "10054" in message or "ConnectionResetError" in exc_str or "10054" in exc_str:
                    return  # silently ignore
                loop.default_exception_handler(context)
            loop.set_exception_handler(_silent_exception_handler)
        except Exception:
            pass
    yield

app = FastAPI(title=f"{APP_NAME} backend", version=APP_VERSION, lifespan=lifespan)

ALLOWED_BROWSER_ORIGINS = {
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "tauri://localhost",
    "http://tauri.localhost",
}


def _referer_origin(referer: str | None) -> str | None:
    if not referer:
        return None
    parsed = urlparse(referer)
    if not parsed.scheme or not parsed.netloc:
        return None
    return f"{parsed.scheme}://{parsed.netloc}"


@app.middleware("http")
async def reject_untrusted_browser_origins(request: Request, call_next):
    origin = request.headers.get("origin") or _referer_origin(request.headers.get("referer"))
    if origin and origin not in ALLOWED_BROWSER_ORIGINS:
        return JSONResponse({"detail": "Forbidden origin"}, status_code=403)
    return await call_next(request)

# Setup CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=sorted(ALLOWED_BROWSER_ORIGINS),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(settings_router)
app.include_router(project_router)
app.include_router(pages_router)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8000, help="Port to run the API server on")
    args = parser.parse_args()

    logger.info("Starting FastAPI server on port %d", args.port)
    uvicorn.run(app, host="127.0.0.1", port=args.port)
