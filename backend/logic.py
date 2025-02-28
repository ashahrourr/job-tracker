# backend/logic.py
import spacy
from backend.database import JobApplication
import os

MODEL_PATH = os.path.join(os.path.dirname(__file__), "job_extractor_model") 

def insert_job_applications(db, confirmations):
    """
    Load spaCy, parse each email for company/position,
    insert into DB, ensure every confirmation email is recorded.
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

        # ✅ Ensure company is saved, even if position is missing
        if company:
            new_job = JobApplication(
                company=company, 
                job_title=job_title if job_title else "Unknown Position"  # ✅ Fallback for missing positions
            )
            db.add(new_job)
            processed_count += 1
        else:
            skipped_count += 1  # Skip only if no company is found

    db.commit()
    return processed_count, skipped_count

