import spacy
from backend.workflow_pipeline.database import JobApplication
import os

# Specify the directory of your saved spaCy NER model.
# (If you are versioning your model directories, update this path accordingly.)
MODEL_PATH = os.path.join(os.path.dirname(__file__), "job_extractor_model_v1741654429") 

def insert_job_applications(db, confirmations, user_email: str):
    """
    Load the spaCy NER model, parse each confirmation email to extract the COMPANY and POSITION,
    and insert new job applications into the database for the given user.
    
    Duplicates are skipped if a record with the same company and position already exists.
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

        # Only proceed if a company was detected
        if company:
            effective_title = job_title if job_title else "Unknown Position"
            # Check for duplicates for the specific user
            duplicate = db.query(JobApplication).filter(
                JobApplication.user_email == user_email,
                JobApplication.company == company,
                JobApplication.job_title == effective_title
            ).first()

            if duplicate:
                skipped_count += 1
                continue

            # Insert new job application record
            new_job = JobApplication(user_email=user_email, company=company, job_title=effective_title)
            db.add(new_job)
            processed_count += 1
        else:
            skipped_count += 1

    db.commit()
    return processed_count, skipped_count
