from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from database import SessionLocal, JobApplication
from fastapi.middleware.cors import CORSMiddleware
from auth import router as auth_router
from gmail import router as gmail_router

app = FastAPI()

# Include the auth routes
app.include_router(auth_router)
app.include_router(gmail_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Allow frontend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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

# Get all job applications
@app.get("/jobs/")
def get_jobs(db: Session = Depends(get_db)):
    jobs = db.query(JobApplication).all()
    return jobs

# Add a new job application
@app.post("/jobs/")
def add_job(company: str, job_title: str, db: Session = Depends(get_db)):
    new_job = JobApplication(company=company, job_title=job_title)
    db.add(new_job)
    db.commit()
    return {"message": "Job application added successfully!"}
