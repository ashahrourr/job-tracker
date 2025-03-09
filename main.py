from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.database import SessionLocal, JobApplication
from fastapi.middleware.cors import CORSMiddleware
from backend.auth import router as auth_router
from backend.emails import router as gmail_router
from backend.scheduler import router as scheduler_router
from backend.session import get_current_user
import uvicorn

app = FastAPI()

# Include the auth, Gmail, and scheduler routes
app.include_router(auth_router)
app.include_router(gmail_router)
app.include_router(scheduler_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://job-tracker-frontend-045g.onrender.com",  # Production Frontend
        "http://localhost:5173",  # Local Frontend (React, Next.js, etc.)
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Root endpoint (for testing)
@app.get("/")
def read_root():
    return {"message": "Job Tracker API is running on Fly.io!"}

# Get all job applications (for now, open to all; consider securing it later)
@app.get("/jobs/")
def get_jobs(db: Session = Depends(get_db)):
    jobs = db.query(JobApplication).all()
    return jobs

# Ensure the app listens on 0.0.0.0:8000 for Fly.io
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
