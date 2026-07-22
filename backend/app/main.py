from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import knowledge, metrics, papers, research
from app.core.config import get_settings
from app.core.database import init_db
from app.core.middleware import RateLimitMiddleware
from app.core.observability import track_request
from app.core.tracing import setup_tracing

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Local dev: create tables directly. Production deployments should run
    # Alembic migrations instead (see backend/alembic/) and this call
    # becomes a no-op check against an already-migrated schema.
    await init_db()
    yield


app = FastAPI(
    title=settings.APP_NAME,
    description="The Autonomous AI Scientist -- research discovery, PDF intelligence, and knowledge extraction platform.",
    version="0.5.0",
    lifespan=lifespan,
)

setup_tracing(app)  # no-op unless OTEL_EXPORTER_OTLP_ENDPOINT is set

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RateLimitMiddleware)


@app.middleware("http")
async def observability_middleware(request, call_next):
    return await track_request(request, call_next)


app.include_router(papers.router)
app.include_router(knowledge.router)
app.include_router(research.router)
app.include_router(metrics.router)


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": settings.APP_NAME, "phase": 4}
