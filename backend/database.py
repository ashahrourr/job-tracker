# database.py
from sqlalchemy import create_engine, Column, String, Integer, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv
import datetime

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
 
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# UPDATED: JobApplication model now includes a user_email column
class JobApplication(Base):
    __tablename__ = "job_applications"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_email = Column(String, nullable=False)  # NEW: Associate job application with a user
    company = Column(String, nullable=False)
    job_title = Column(String, nullable=False)
    applied_date = Column(DateTime, default=datetime.datetime.utcnow)

# TokenStore remains as before
class TokenStore(Base):
    __tablename__ = "tokens"
    user_id = Column(String, primary_key=True)  # Use user's email (or unique ID) as the key
    token = Column(String, nullable=False)
    refresh_token = Column(String, nullable=False)
    token_uri = Column(String, nullable=False)
    client_id = Column(String, nullable=False)
    client_secret = Column(String, nullable=False)
    scopes = Column(String, nullable=False)

# Create tables (or run migrations)
Base.metadata.create_all(bind=engine)
