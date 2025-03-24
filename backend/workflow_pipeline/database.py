# database.py
from sqlalchemy import create_engine, Column, String, Integer, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv
import datetime

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

# Async engine and session
engine = create_async_engine(DATABASE_URL)
SessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)

Base = declarative_base()

class JobApplication(Base):
    __tablename__ = "job_applications"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_email = Column(String, nullable=False)
    company = Column(String, nullable=False)
    job_title = Column(String, nullable=False)
    applied_date = Column(DateTime, default=datetime.datetime.utcnow)

class TokenStore(Base):
    __tablename__ = "tokens"
    user_id = Column(String, primary_key=True)
    token = Column(String, nullable=False)
    refresh_token = Column(String, nullable=False)
    token_uri = Column(String, nullable=False)
    client_id = Column(String, nullable=False)
    client_secret = Column(String, nullable=False)
    scopes = Column(String, nullable=False)

async def init_models():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)