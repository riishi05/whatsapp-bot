import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.database import ensure_indexes
from app.routers import broadcast, dashboard, dev, webhook
from app.tenant_resolver import refresh_mapping

settings = get_settings()
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Multi-Tenant WhatsApp Agent Orchestrator")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(webhook.router)
app.include_router(dashboard.router)
app.include_router(broadcast.router)
app.include_router(dev.router)


@app.on_event("startup")
async def on_startup():
    await ensure_indexes()
    await refresh_mapping()


@app.get("/health")
async def health():
    return {"status": "ok"}


# Serve the built React dashboard (single-container Cloud Run deployment).
# Falls back gracefully if the static build isn't present (e.g. local `uvicorn`
# dev runs where the frontend is served separately by `npm run dev`).
_static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(_static_dir):
    app.mount("/", StaticFiles(directory=_static_dir, html=True), name="static")
