from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from database import SessionLocal, JobApplication
from fastapi.middleware.cors import CORSMiddleware
from auth import router as auth_router
from emails import router as gmail_router

import spacy
from emails import get_gmail_service, fetch_and_classify_emails
app = FastAPI()

# Include the auth routes and Gmail-related routes
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

# New endpoint to process emails and insert job applications into the database
@app.post("/jobs/process")
def process_emails(db: Session = Depends(get_db)):
    # 1. Initialize Gmail service and fetch emails
    try:
        service = get_gmail_service()
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to initialize Gmail service: " + str(e))
    
    try:
        confirmations, rejections = fetch_and_classify_emails(service, max_results=10)
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to fetch and classify emails: " + str(e))
    
    if not confirmations:
        return {"message": "No confirmation emails found."}
    
    # 2. Load the trained spaCy NER model
    try:
        nlp = spacy.load("job_extractor_model")
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to load spaCy model: " + str(e))
    
    processed_count = 0
    skipped_count = 0

    # 3. Process each confirmation email
    for email in confirmations:
        text = email.get("body", "")
        doc = nlp(text)
        company = None
        job_title = None
        
        # Look for the COMPANY and POSITION entities in the email body
        for ent in doc.ents:
            if ent.label_ == "COMPANY" and not company:
                company = ent.text
            elif ent.label_ == "POSITION" and not job_title:
                job_title = ent.text
        
        if company and job_title:
            new_job = JobApplication(company=company, job_title=job_title)
            db.add(new_job)
            processed_count += 1
        else:
            skipped_count += 1

    db.commit()
    return {
        "message": f"Processed {processed_count} emails and inserted into the database. Skipped {skipped_count} emails due to missing entities."
    }
