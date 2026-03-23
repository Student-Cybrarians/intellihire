"""
app/main.py — IntelliHire on Microsoft Azure
Stack: Azure App Service + Azure Cosmos DB + Azure OpenAI + Azure Static Web Apps
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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger("intellihire")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"🚀 Starting {settings.APP_NAME} v{settings.APP_VERSION} on Azure")
    logger.info(f"🗄️  Database: Azure Cosmos DB (MongoDB API)")
    logger.info(f"🤖 LLM: {settings.LLM_PROVIDER} — {settings.AZURE_OPENAI_DEPLOYMENT or settings.OPENAI_MODEL}")
    await init_db()
    yield
    logger.info("🛑 Shutting down...")
    await close_db()


def create_app() -> FastAPI:
    app = FastAPI(
        title="IntelliHire — AI Placement Trainer (Microsoft Azure)",
        description="""
## IntelliHire — Powered by Microsoft Azure

**Infrastructure:**
- 🌐 **Frontend**: Azure Static Web Apps
- ⚡ **Backend**: Azure App Service (Python/FastAPI)
- 🗄️ **Database**: Azure Cosmos DB (MongoDB API)
- 🤖 **AI/LLM**: Azure OpenAI (GPT-4o)
- 📁 **Storage**: Azure Blob Storage
- 🔄 **CI/CD**: GitHub Actions (Microsoft)

**Module 1 Endpoints:**
- `POST /api/v1/resume/upload_resume`
- `POST /api/v1/resume/analyze`
- `POST /api/v1/resume/generate_resume`
        """,
        version=settings.APP_VERSION,
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.get_allowed_origins(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def timing(request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        response.headers["X-Process-Time"] = f"{time.perf_counter()-start:.3f}s"
        response.headers["X-Powered-By"] = "Microsoft Azure"
        return response

    @app.exception_handler(IntelliHireException)
    async def intellihire_handler(request: Request, exc: IntelliHireException):
        return JSONResponse(status_code=exc.status_code,
                           content={"error": exc.__class__.__name__, "message": exc.message})

    @app.exception_handler(Exception)
    async def generic_handler(request: Request, exc: Exception):
        logger.exception(f"Unhandled error: {exc}")
        return JSONResponse(status_code=500,
                           content={"error": "InternalServerError", "message": str(exc)})

    from app.api.v1.endpoints.resume import router as resume_router
    app.include_router(resume_router, prefix="/api/v1")

    @app.get("/health", tags=["System"])
    async def health():
        return {
            "status": "ok",
            "service": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "platform": "Microsoft Azure",
            "services": {
                "database": "Azure Cosmos DB (MongoDB API)",
                "llm": f"Azure OpenAI — {settings.AZURE_OPENAI_DEPLOYMENT or 'GPT-4o'}",
                "storage": "Azure Blob Storage" if settings.USE_AZURE_STORAGE else "Local /tmp",
                "hosting": "Azure App Service",
            }
        }

    @app.get("/", tags=["System"])
    async def root():
        return {"message": f"Welcome to {settings.APP_NAME}", "docs": "/docs",
                "powered_by": "Microsoft Azure"}

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=settings.DEBUG)
