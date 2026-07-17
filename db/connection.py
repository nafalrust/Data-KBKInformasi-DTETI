from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from config import DATABASE_URL


def get_engine() -> AsyncEngine:
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL belum diset — isi .env dari .env.example")
    return create_async_engine(DATABASE_URL, echo=False)


def get_sessionmaker(engine: AsyncEngine) -> async_sessionmaker:
    return async_sessionmaker(engine, expire_on_commit=False)
