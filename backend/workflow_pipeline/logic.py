# logic.py (updated)
import spacy
from sqlalchemy import select, insert
from sqlalchemy.dialects.postgresql import insert as pg_insert
from backend.workflow_pipeline.database import JobApplication, AsyncSession
import os
from typing import List, Dict

MODEL_PATH = os.path.join(os.path.dirname(__file__), "job_extractor_model_v1741654429")

# ✅ Load spaCy model ONCE at startup
try:
    nlp = spacy.load(MODEL_PATH)
except Exception as e:
    raise RuntimeError(f"Failed to load spaCy model: {str(e)}")

async def insert_job_applications(db: AsyncSession, confirmations: List[Dict], user_email: str) -> tuple[int, int]:
    """
    Async version with batch processing and PostgreSQL upsert.
    Returns: (processed_count, skipped_count)
    """
    processed = 0
    skipped = 0
    batch = []

    for email in confirmations:
        text = email.get("body", "")
        doc = nlp(text)  # ✅ Reuse preloaded model
        
        company = next((ent.text for ent in doc.ents if ent.label_ == "COMPANY"), None)
        job_title = next((ent.text for ent in doc.ents if ent.label_ == "POSITION"), None) or "Unknown Position"

        if not company:
            skipped += 1
            continue

        batch.append({
            "user_email": user_email,
            "company": company,
            "job_title": job_title
        })

    if not batch:
        return 0, skipped

    # ✅ Bulk insert with conflict skipping (PostgreSQL specific)
    stmt = pg_insert(JobApplication.__table__).values(batch).on_conflict_do_nothing(
        index_elements=["user_email", "company", "job_title"]
    )
    
    result = await db.execute(stmt)
    await db.commit()
    
    processed = result.rowcount  # Number of inserted rows
    skipped += len(batch) - processed  # Conflicts + no-company entries
    
    return processed, skipped