import argparse
import asyncio
import logging
import os
import sys
from contextlib import asynccontextmanager
from urllib.parse import urlparse

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Add backend directory to sys.path to ensure local imports resolve.
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# Text layout uses QFontMetricsF in request handlers, so the backend process
# needs an offscreen QApplication before routes start serving bubble data.
import infrastructure.runtime.qt  # noqa: F401

from core.version import APP_NAME, __version__ as APP_VERSION
from core.container import build_container
from core.errors import PageImageLoadError, PageNotFoundError
from infrastructure.logging import configure_logging
from api.routes.jobs import router as jobs_router
from api.routes.pages import router as pages_router
from api.routes.project import router as project_router
from api.routes.settings import router as settings_router


configure_logging()
logger = logging.getLogger(APP_NAME)

ALLOWED_BROWSER_ORIGINS = {
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "tauri://localhost",
    "http://tauri.localhost",
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Suppress harmless ConnectionResetError on Windows during shutdown.
    if sys.platform == "win32":
        try:
            loop = asyncio.get_running_loop()

            def _silent_exception_handler(loop, context):
                message = context.get("message", "")
                exception = context.get("exception")
                exc_str = str(exception) if exception else ""
                if "ConnectionResetError" in message or "10054" in message or "ConnectionResetError" in exc_str or "10054" in exc_str:
                    return
                loop.default_exception_handler(context)

            loop.set_exception_handler(_silent_exception_handler)
        except Exception:
            pass
    yield


def _referer_origin(referer: str | None) -> str | None:
    if not referer:
        return None
    parsed = urlparse(referer)
    if not parsed.scheme or not parsed.netloc:
        return None
    return f"{parsed.scheme}://{parsed.netloc}"


async def reject_untrusted_browser_origins(request: Request, call_next):
    origin = request.headers.get("origin") or _referer_origin(request.headers.get("referer"))
    if origin and origin not in ALLOWED_BROWSER_ORIGINS:
        return JSONResponse({"detail": "Forbidden origin"}, status_code=403)
    return await call_next(request)


def include_routes(app: FastAPI) -> None:
    app.include_router(settings_router)
    app.include_router(project_router)
    app.include_router(pages_router)
    app.include_router(jobs_router)


async def _page_not_found_handler(request: Request, exc: PageNotFoundError):
    return JSONResponse({"detail": "Page not found"}, status_code=404)


async def _page_image_load_handler(request: Request, exc: PageImageLoadError):
    return JSONResponse({"detail": "Failed to load page image"}, status_code=500)


def create_app() -> FastAPI:
    app = FastAPI(title=f"{APP_NAME} backend", version=APP_VERSION, lifespan=lifespan)
    app.state.container = build_container()
    app.add_exception_handler(PageNotFoundError, _page_not_found_handler)
    app.add_exception_handler(PageImageLoadError, _page_image_load_handler)
    app.middleware("http")(reject_untrusted_browser_origins)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=sorted(ALLOWED_BROWSER_ORIGINS),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    include_routes(app)
    return app


app = create_app()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8000, help="Port to run the API server on")
    args = parser.parse_args()

    logger.info("Starting FastAPI server on port %d", args.port)
    uvicorn.run(app, host="127.0.0.1", port=args.port)
