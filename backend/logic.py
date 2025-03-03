# backend/logic.py
import spacy
from backend.database import JobApplication
import os

MODEL_PATH = os.path.join(os.path.dirname(__file__), "job_extractor_model") 

def insert_job_applications(db, confirmations):
    """
    Load spaCy, parse each email for company/position,
    insert into DB, ensuring each confirmation email is recorded.
    Skip duplicates if the same company and position already exist.
    """

    try:
        nlp = spacy.load(MODEL_PATH)
    except Exception as e:
        raise RuntimeError(f"Failed to load spaCy model: {str(e)}")
    
    processed_count = 0
    skipped_count = 0

    for email in confirmations:
        text = email.get("body", "")
        doc = nlp(text)
        company = None
        job_title = None
        
        for ent in doc.ents:
            if ent.label_ == "COMPANY" and not company:
                company = ent.text
            elif ent.label_ == "POSITION" and not job_title:
                job_title = ent.text

        # Ensure company is present to proceed
        if company:
            # Use a fallback for job_title if it's not extracted
            effective_title = job_title if job_title else "Unknown Position"

            # Check for duplicates: same company and same position already in the DB
            duplicate = db.query(JobApplication).filter(
                JobApplication.company == company,
                JobApplication.job_title == effective_title
            ).first()

            if duplicate:
                # Duplicate found, skip this record
                skipped_count += 1
                continue

            # Create new job application record if it's not a duplicate
            new_job = JobApplication(company=company, job_title=effective_title)
            db.add(new_job)
            processed_count += 1
        else:
            skipped_count += 1  # Skip if no company is found

    db.commit()
    return processed_count, skipped_count

