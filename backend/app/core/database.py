"""
app/core/database.py
──────────────────────
Async MongoDB connection using Motor + Beanie ODM.
Call init_db() once on FastAPI startup.
"""

import logging
from typing import Optional

from beanie import init_beanie
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.core.config import settings

logger = logging.getLogger(__name__)

# Module-level client so we can close it gracefully on shutdown
_client: Optional[AsyncIOMotorClient] = None


async def init_db() -> None:
    """
    Initialise Motor client and Beanie ODM.
    Import all Document models here so Beanie registers them.
    """
    global _client

    # Import document models (circular-import safe — done inside function)
    from app.models.resume import ResumeDocument
    from app.models.analysis import AnalysisDocument
    from app.models.job_description import JobDescriptionDocument

    _client = AsyncIOMotorClient(
        settings.MONGODB_URL,
        serverSelectionTimeoutMS=5000,  # fail fast if Mongo is unreachable
    )

    await init_beanie(
        database=_client[settings.MONGODB_DB_NAME],
        document_models=[
            ResumeDocument,
            AnalysisDocument,
            JobDescriptionDocument,
        ],
    )

    logger.info(f"✅ MongoDB connected: {settings.MONGODB_DB_NAME}")


async def close_db() -> None:
    """Gracefully close the Motor client on app shutdown."""
    global _client
    if _client:
        _client.close()
        logger.info("MongoDB connection closed.")


def get_database() -> AsyncIOMotorDatabase:
    """Return raw Motor database (for operations outside Beanie)."""
    if _client is None:
        raise RuntimeError("Database not initialised. Call init_db() first.")
    return _client[settings.MONGODB_DB_NAME]
