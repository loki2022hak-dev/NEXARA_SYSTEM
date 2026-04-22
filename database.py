from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True)
    username = Column(String)
    token = Column(String, unique=True)
    expires_at = Column(DateTime)
    status = Column(String, default="active")

class Stat(Base):
    __tablename__ = "stats"
    id = Column(Integer, primary_key=True)
    date = Column(DateTime, default=datetime.utcnow)
    api_requests = Column(Integer, default=0)

engine = create_async_engine("sqlite+aiosqlite:///nexara.db")
async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
