"""
app/main.py
────────────
FastAPI application factory for IntelliHire Module 1.

Startup sequence:
  1. Load settings from .env
  2. Connect to MongoDB (Beanie init)
  3. Register exception handlers
  4. Mount API routers
  5. Add CORS middleware
"""

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.database import close_db, init_db
from app.core.exceptions import IntelliHireException

# Configure logging
logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("intellihire")


# ─────────────────────────────────────────────────────────
# Lifespan (startup + shutdown)
# ─────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle: startup and shutdown tasks."""
    logger.info(f"🚀 Starting {settings.APP_NAME} v{settings.APP_VERSION} [{settings.ENVIRONMENT}]")
    await init_db()
    yield
    logger.info("🛑 Shutting down…")
    await close_db()


# ─────────────────────────────────────────────────────────
# App factory
# ─────────────────────────────────────────────────────────

def create_app() -> FastAPI:
    app = FastAPI(
        title=f"{settings.APP_NAME} – Module 1: ATS Resume Analyzer",
        description="""
## IntelliHire — AI Placement Trainer

**Module 1: ATS Resume Analyzer & Generator**

Endpoints:
- `POST /api/v1/resume/upload_resume` — Upload PDF/DOCX, extract structured data
- `POST /api/v1/resume/analyze`       — ATS score, keyword gap, LLM suggestions
- `POST /api/v1/resume/generate_resume` — Generate ATS-friendly resume PDF

Built with FastAPI · spaCy · sentence-transformers · MongoDB · OpenAI/Claude
        """,
        version=settings.APP_VERSION,
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # ── CORS ──────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.get_allowed_origins(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Request timing middleware ─────────────────────────
    @app.middleware("http")
    async def add_process_time_header(request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        duration = time.perf_counter() - start
        response.headers["X-Process-Time"] = f"{duration:.3f}s"
        return response

    # ── Exception handlers ────────────────────────────────
    @app.exception_handler(IntelliHireException)
    async def intellihire_exception_handler(request: Request, exc: IntelliHireException):
        """Convert domain exceptions to structured JSON error responses."""
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error":   exc.__class__.__name__,
                "message": exc.message,
                "path":    str(request.url),
            },
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception):
        logger.exception(f"Unhandled error on {request.url}: {exc}")
        return JSONResponse(
            status_code=500,
            content={
                "error":   "InternalServerError",
                "message": "An unexpected error occurred. Check server logs.",
                "path":    str(request.url),
            },
        )

    # ── Routers ───────────────────────────────────────────
    from app.api.v1.endpoints.resume import router as resume_router
    app.include_router(resume_router, prefix="/api/v1")

    # ── Health check ─────────────────────────────────────
    @app.get("/health", tags=["System"])
    async def health_check():
        return {
            "status": "ok",
            "service": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "environment": settings.ENVIRONMENT,
        }

    @app.get("/", tags=["System"])
    async def root():
        return {
            "message": f"Welcome to {settings.APP_NAME}",
            "docs": "/docs",
            "health": "/health",
        }

    return app


app = create_app()


# ─────────────────────────────────────────────────────────
# Dev runner
# ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level="info",
    )
