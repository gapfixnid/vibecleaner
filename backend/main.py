import argparse
import asyncio
import logging
import os
import sys
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

# This entry point runs in three modes:
#   1. `python -m backend.main`      — repo root already on sys.path
#   2. `python backend/main.py`      — dev Tauri launcher (script mode)
#   3. PyInstaller sidecar entry     — frozen script mode
# In script modes there is no parent package, so register the repo root and
# use absolute `backend.*` imports (the rest of the package stays relative).
if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.infrastructure.runtime.qt import QtRuntime

from backend.core.version import APP_NAME, __version__ as APP_VERSION
from backend.core.container import build_container, start_pipeline_warmup
from backend.core.errors import PageImageLoadError, PageNotFoundError
from backend.infrastructure.logging import configure_logging
from backend.api.routes.jobs import router as jobs_router
from backend.api.routes.catalog import router as catalog_router
from backend.api.routes.pages import router as pages_router
from backend.api.routes.project import router as project_router
from backend.api.routes.settings import router as settings_router
from backend.api.routes.health import router as health_router
from backend.api.security import SESSION_TOKEN_ENV, SessionAuthMiddleware, canonical_token


configure_logging()
logger = logging.getLogger(APP_NAME)

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
    try:
        yield
    finally:
        container = getattr(app.state, "container", None)
        detection_service = getattr(container, "detection_service", None)
        shutdown = getattr(detection_service, "shutdown", None)
        if callable(shutdown):
            shutdown()


def include_routes(app: FastAPI) -> None:
    app.include_router(health_router)
    app.include_router(catalog_router)
    app.include_router(settings_router)
    app.include_router(project_router)
    app.include_router(pages_router)
    app.include_router(jobs_router)


async def _page_not_found_handler(request: Request, exc: PageNotFoundError):
    return JSONResponse({"detail": "Page not found"}, status_code=404)


async def _page_image_load_handler(request: Request, exc: PageImageLoadError):
    return JSONResponse({"detail": "Failed to load page image"}, status_code=500)


def create_app(session_token: str, qt_runtime: QtRuntime | None = None) -> FastAPI:
    token_bytes = canonical_token(session_token)
    runtime = qt_runtime or QtRuntime.initialize_on_main_thread()
    app = FastAPI(
        title=f"{APP_NAME} backend",
        version=APP_VERSION,
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.session_token_bytes = token_bytes
    app.state.qt_runtime = runtime
    app.state.container = build_container(qt_runtime=runtime)
    app.add_exception_handler(PageNotFoundError, _page_not_found_handler)
    app.add_exception_handler(PageImageLoadError, _page_image_load_handler)
    app.add_middleware(SessionAuthMiddleware)
    include_routes(app)
    return app


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8000, help="Port to run the API server on")
    args = parser.parse_args()

    session_token = os.environ.pop(SESSION_TOKEN_ENV, None)
    if session_token is None:
        logger.critical("Missing local backend session token")
        raise SystemExit(2)
    qt_runtime = QtRuntime.initialize_on_main_thread()
    try:
        app = create_app(session_token, qt_runtime)
    except ValueError as exc:
        logger.critical("Invalid local backend session token: %s", exc)
        raise SystemExit(2) from exc
    try:
        start_pipeline_warmup(app.state.container)
        logger.info("Starting FastAPI server on port %d", args.port)
        uvicorn.run(app, host="127.0.0.1", port=args.port)
    finally:
        qt_runtime.shutdown_on_main_thread()
