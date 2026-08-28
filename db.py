from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from config import settings


class Base(DeclarativeBase):
    pass


engine = create_async_engine(settings.DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, expire_on_commit=False)


async def init_db() -> None:
    """Create tables if they don't exist yet. Call once on startup.
    For real migrations later, swap this for Alembic."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncSession:
    async with async_session() as session:
        yield session
