# logic.py
from sqlalchemy import insert
from sqlalchemy.dialects.postgresql import insert as pg_insert
from backend.workflow_pipeline.database import JobApplication, AsyncSession
from typing import List, Dict

async def insert_job_applications(
    db: AsyncSession, 
    applications: List[Dict[str, str]],
    user_email: str
) -> tuple[int, int]:
    """
    Pure database operation - expects pre-processed data
    Args:
        applications: List of dicts with 'company' and 'position' keys
    """
    if not applications:
        return 0, 0

    batch = [{
        "user_email": user_email,
        "company": app["company"],
        # Changed from "position" to "job_title"
        "job_title": app["job_title"] or "Unknown Position"  # 🚨 CORRECTION
    } for app in applications]

    # Upsert logic
    stmt = pg_insert(JobApplication.__table__).values(batch).on_conflict_do_nothing(
        index_elements=["user_email", "company", "job_title"]
    )
    
    result = await db.execute(stmt)
    await db.commit()
    
    processed = result.rowcount
    skipped = len(batch) - processed
    
    return processed, skipped