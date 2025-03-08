from sqlalchemy import create_engine, Column, String, Integer, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv
import datetime

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

# ✅ Ensure Supabase uses SSL for secure connection
if DATABASE_URL and "supabase.co" in DATABASE_URL:
    DATABASE_URL += "?sslmode=require"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# ✅ Job Application Model
class JobApplication(Base):
    __tablename__ = "job_applications"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_email = Column(String, nullable=False)  # Associate job application with a user
    company = Column(String, nullable=False)
    job_title = Column(String, nullable=False)
    applied_date = Column(DateTime, default=datetime.datetime.utcnow)

# ✅ TokenStore Model
class TokenStore(Base):
    __tablename__ = "tokens"
    user_id = Column(String, primary_key=True)  # Use user's email (or unique ID) as the key
    token = Column(String, nullable=False)
    refresh_token = Column(String, nullable=False)
    token_uri = Column(String, nullable=False)
    client_id = Column(String, nullable=False)
    client_secret = Column(String, nullable=False)
    scopes = Column(String, nullable=False)

# ✅ Create Tables in Supabase (if not existing)
Base.metadata.create_all(bind=engine)
