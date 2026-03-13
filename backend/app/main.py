from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.data_quality import router as data_quality_router
from app.api.routes.reconcile import router as reconcile_router
from app.core.config import settings
from app.core.errors import register_error_handlers
from app.core.logging import configure_logging


configure_logging()
app = FastAPI(title=settings.app_name)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", settings.frontend_api_base_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
register_error_handlers(app)
app.include_router(reconcile_router)
app.include_router(data_quality_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "app": settings.app_name}
