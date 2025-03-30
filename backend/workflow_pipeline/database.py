# database.py
from sqlalchemy import create_engine, Column, String, Integer, DateTime, Index, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import async_scoped_session
import asyncio
import os
from dotenv import load_dotenv
import datetime


load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

# Async engine and session
engine = create_async_engine(
    DATABASE_URL,
    pool_size=20,        # Number of persistent connections
    max_overflow=10,     # Additional connections allowed during spikes
    pool_timeout=30,     # Max time to wait for a connection
    pool_recycle=1800,    # Recycle connections every 30 mins (prevents timeouts)
    pool_pre_ping=True 
)

SessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)

async_session = async_scoped_session(SessionLocal, scopefunc=asyncio.current_task)

Base = declarative_base()

class JobApplication(Base):
    __tablename__ = "job_applications"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_email = Column(String, nullable=False)
    company = Column(String, nullable=False)
    job_title = Column(String, nullable=False)
    applied_date = Column(DateTime, default=datetime.datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("user_email", "company", "job_title", name="uix_user_company_job"),
    )

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
        
