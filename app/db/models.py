from sqlalchemy import Column, Integer, String, DateTime, BigInteger
from app.db.database import Base
import datetime

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    tg_id = Column(BigInteger, unique=True, index=True)
    tier = Column(String, default="GUEST") # GUEST, LITE, PRO, ELITE
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class SearchHistory(Base):
    __tablename__ = "search_history"
    id = Column(Integer, primary_key=True, index=True)
    tg_id = Column(BigInteger, index=True)
    target = Column(String)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
