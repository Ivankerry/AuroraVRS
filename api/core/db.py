import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from core.config import get_settings
import redis.asyncio as redis
import logging

logger = logging.getLogger(__name__)
settings = get_settings()

# Critical: Configure connection pool for multi-user streaming app
# pool_size: number of persistent connections to keep open
# max_overflow: additional connections allowed when pool is exhausted
# pool_pre_ping: test connection health before using
# pool_recycle: recycle connections after 1 hour to avoid stale connections
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_POOL_OVERFLOW,
    pool_pre_ping=True,
    pool_recycle=3600,
)

logger.info(f"Database connection pool configured: pool_size={settings.DB_POOL_SIZE}, max_overflow={settings.DB_POOL_OVERFLOW}")

AsyncSessionLocal = async_sessionmaker(
    bind=engine, class_=AsyncSession, expire_on_commit=False
)

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

async def get_redis():
    return redis.from_url(settings.REDIS_URL)
