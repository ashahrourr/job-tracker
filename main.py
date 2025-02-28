from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.database import SessionLocal, JobApplication
from fastapi.middleware.cors import CORSMiddleware
from backend.auth import router as auth_router
from backend.emails import router as gmail_router, get_gmail_service, fetch_and_classify_emails
import spacy
from backend.logic import insert_job_applications 
from backend.scheduler import daily_email_fetch_job

app = FastAPI()

# Include the auth routes and Gmail-related routes
app.include_router(auth_router)
app.include_router(gmail_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://job-tracker-frontend-045g.onrender.com"],  # Allow your frontend
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
    return {"message": "Job Tracker API is running with scheduled email fetch!"}

# Get all job applications
@app.get("/jobs/")
def get_jobs(db: Session = Depends(get_db)):
    jobs = db.query(JobApplication).all()
    return jobs

# Manual email processing endpoint
@app.post("/jobs/process")
def process_emails(db: Session = Depends(get_db)):
    # 1. Get Gmail service
    try:
        service = get_gmail_service()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to initialize Gmail service: {str(e)}")
    
    # 2. Fetch and classify
    try:
        confirmations, rejections = fetch_and_classify_emails(service)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch and classify emails: {str(e)}")
    
    if not confirmations:
        return {"message": "No confirmation emails found."}
    
    # 3. Insert into DB (moved the spacy logic into backend/logic.py)
    try:
        processed_count, skipped_count = insert_job_applications(db, confirmations)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {
        "message": f"Processed {processed_count} emails. Skipped {skipped_count}."
    }

@app.get("/test-fetch")
def test_fetch():
    daily_email_fetch_job()  # ✅ Manually trigger the job
    return {"message": "Manually triggered job"}

@app.get("/cron-trigger")
def cron_trigger():
    daily_email_fetch_job()
    return {"message": "Job triggered via Render Cron at 11:59 PM"}


# ✅ Step 4: Start the Scheduler on FastAPI Startup
@app.on_event("startup")
def on_startup():
    print("on start is working in main")
    from backend.scheduler import start_scheduler
    start_scheduler()
    print("start scheduler called")
