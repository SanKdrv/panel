"""FastAPI application entry point."""
from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import make_asgi_app

from .config import get_settings
from .logging_config import configure_logging, reset_request_id, set_request_id
from .routers import auth, documents, generate, leads, mautic, prompts, quality, system
from .services.metrics import HTTP_REQUESTS
from .services.rag_client_factory import shutdown_rag_client

settings = get_settings()
configure_logging(settings.log_level)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("event=app.starting rag_backend_url=%s", settings.rag_backend_url)
    yield
    logger.info("event=app.stopping")
    await shutdown_rag_client()


app = FastAPI(
    title="RAG Admin Panel Backend",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/metrics", make_asgi_app())


@app.middleware("http")
async def access_log_and_request_id(request: Request, call_next):
    rid = request.headers.get("x-request-id", str(uuid4()))
    token = set_request_id(rid)
    started = time.perf_counter()
    path = request.url.path
    should_log = settings.http_access_log and path != "/metrics"

    if should_log:
        logger.info("event=http.start method=%s path=%s", request.method, path)
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("event=http.error method=%s path=%s", request.method, path)
        reset_request_id(token)
        raise

    duration_ms = round((time.perf_counter() - started) * 1000, 2)
    response.headers["x-request-id"] = rid
    HTTP_REQUESTS.labels(
        method=request.method,
        path=path,
        status=str(response.status_code),
    ).inc()

    if should_log:
        logger.info(
            "event=http.done method=%s path=%s status=%s duration_ms=%s",
            request.method,
            path,
            response.status_code,
            duration_ms,
        )

    reset_request_id(token)
    return response


@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok"}


# Routers
app.include_router(auth.router)
app.include_router(system.router)
app.include_router(documents.router)
app.include_router(prompts.router)
app.include_router(generate.router)
app.include_router(leads.router)
app.include_router(mautic.router)
app.include_router(quality.router)
