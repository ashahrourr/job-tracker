from sqlalchemy import create_engine, Column, String, Integer
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

# Create database connection
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Job Application Model
class JobApplication(Base):
    __tablename__ = "job_applications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    company = Column(String, nullable=False)
    job_title = Column(String, nullable=False)
    applied_date = Column(String, nullable=False)

# ✅ New Table: Store Gmail API Tokens
class TokenStore(Base):
    __tablename__ = "tokens"

    id = Column(String, primary_key=True, default="gmail")  # Fixed ID to avoid duplicates
    token = Column(String, nullable=False)
    refresh_token = Column(String, nullable=False)
    token_uri = Column(String, nullable=False)
    client_id = Column(String, nullable=False)
    client_secret = Column(String, nullable=False)
    scopes = Column(String, nullable=False)

# ✅ Create Tables in PostgreSQL
Base.metadata.create_all(bind=engine)
