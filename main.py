from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.database import SessionLocal, JobApplication
from fastapi.middleware.cors import CORSMiddleware
from backend.auth import router as auth_router
from backend.emails import router as gmail_router
from backend.scheduler import router as scheduler_router
from backend.session import get_current_user

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
    return {"message": "Job Tracker API is running!"}

# Get all job applications (for now, open to all; consider securing it later)
@app.get("/jobs/")
def get_jobs(db: Session = Depends(get_db)):
    jobs = db.query(JobApplication).all()
    return jobs

# (Optional) Manual email processing endpoint for the logged-in user
# This is an alternative to using the GET /my-email-fetch endpoint in scheduler.py.
# Uncomment if you want a POST endpoint in main.py as well.
# @app.post("/jobs/process")
# def process_emails(current_user: str = Depends(get_current_user), db: Session = Depends(get_db)):
#     from backend.scheduler import process_user_emails
#     try:
#         results = process_user_emails(current_user)
#         return {
#             "message": f"Processed emails for {current_user}.",
#             "details": results
#         }
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))
