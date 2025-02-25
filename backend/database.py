from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import datetime
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get the database connection URL from .env
DATABASE_URL = os.getenv("DATABASE_URL")

# Create database connection
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base model for our tables
Base = declarative_base()

# Job Application Model
class JobApplication(Base):
    __tablename__ = "job_applications"

    id = Column(Integer, primary_key=True, index=True)
    company = Column(String, nullable=False)
    job_title = Column(String, nullable=False)
    applied_date = Column(DateTime, default=datetime.datetime.utcnow)

# Create tables in PostgreSQL database
Base.metadata.create_all(bind=engine)