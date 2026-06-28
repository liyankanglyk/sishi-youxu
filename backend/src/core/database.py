"""异步 SQLAlchemy 引擎与会话工厂。

骨架：声明引擎、会话工厂以及 `get_db()` 依赖。
模型通过 src.models.__init__ 注册到 `Base.metadata`。
"""
from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.core.config import settings

# 由 src.models.__init__ 延迟导入以注册表。
from src.models.base import Base  # noqa: F401  （为调用方重新导出）


engine: AsyncEngine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DB_ECHO,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_recycle=settings.DB_POOL_RECYCLE,
    pool_pre_ping=True,
    future=True,
)

AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI 依赖，产生一个事务性的异步 session。"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """创建所有表。骨架辅助函数；生产环境将使用 Alembic。"""
    # 导入模型，使其在 create_all 之前注册到 Base.metadata。
    from src import models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """释放引擎连接池。"""
    await engine.dispose()