import datetime
import logging
from typing import List, Dict, Tuple
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from backend.workflow_pipeline.database import JobApplication

logger = logging.getLogger(__name__)

# Configuration for database operations
DB_CONFIG = {
    "batch_size": 50,          # Number of records per insert batch
    "max_retries": 3,          # Maximum retry attempts for DB operations
    "retry_wait": 1,           # Initial retry wait time in seconds
    "retry_backoff": 2,        # Backoff multiplier for retries
    "unknown_placeholder": "unknown position",
    "commit_interval": 25      # How often to commit during large batches
}

async def insert_job_applications(
    db: AsyncSession, 
    applications: List[Dict[str, str]],
    user_email: str
) -> Tuple[int, int]:
    """Process and insert job applications with enhanced robustness"""
    if not applications:
        logger.info("No applications to process")
        return 0, 0

    try:
        # Step 1: Deduplicate and validate entries
        valid_apps = await _process_entries(applications, user_email)
        
        # Step 2: Batch processing with retries
        total_processed = 0
        batch_size = DB_CONFIG["batch_size"]
        
        for batch_idx in range(0, len(valid_apps), batch_size):
            batch = valid_apps[batch_idx:batch_idx + batch_size]
            processed = await _process_batch_with_retry(db, batch)
            total_processed += processed
            
            # Intermediate commit for large datasets
            if batch_idx % DB_CONFIG["commit_interval"] == 0:
                await db.commit()
                logger.debug(f"Intermediate commit after {batch_idx} records")

        await db.commit()
        skipped = len(valid_apps) - total_processed
        
        logger.info(f"Inserted {total_processed} applications, skipped {skipped}")
        return total_processed, skipped

    except Exception as e:
        await db.rollback()
        logger.error(f"Transaction failed: {str(e)}")
        return 0, len(applications)

async def _process_entries(applications: List[Dict], user_email: str) -> List[Dict]:
    """Deduplicate and validate application entries"""
    company_map = {}
    
    for app in applications:
        raw_company = app.get("company", "").strip()
        raw_title = app.get("job_title", "").strip().lower()
        
        if not raw_company:
            continue
            
        company_key = raw_company.lower()
        job_title = raw_title or DB_CONFIG["unknown_placeholder"]
        
        # Keep best version (prefer known positions)
        existing = company_map.get(company_key)
        if not existing or (existing["job_title"] == DB_CONFIG["unknown_placeholder"] 
                          and job_title != DB_CONFIG["unknown_placeholder"]):
            company_map[company_key] = {
                "user_email": user_email,
                "company": company_key,
                "job_title": job_title,
                "applied_date": datetime.datetime.utcnow()
            }

    return list(company_map.values())

@retry(
    stop=stop_after_attempt(DB_CONFIG["max_retries"]),
    wait=wait_exponential(
        multiplier=DB_CONFIG["retry_backoff"], 
        min=DB_CONFIG["retry_wait"]
    ),
    retry=retry_if_exception_type(Exception),
    before_sleep=lambda _: logger.warning("Retrying batch insert...")
)
async def _process_batch_with_retry(db: AsyncSession, batch: List[Dict]) -> int:
    """Process a batch with retry logic"""
    try:
        # Separate known and unknown positions
        known_entries, unknown_entries = [], []
        for entry in batch:
            if entry["job_title"] != DB_CONFIG["unknown_placeholder"]:
                known_entries.append(entry)
            else:
                unknown_entries.append(entry)

        # Check for existing known positions
        if unknown_entries:
            await _filter_conflicting_unknowns(db, unknown_entries)

        final_batch = known_entries + unknown_entries
        if not final_batch:
            return 0

        return await _execute_batch_insert(db, final_batch)

    except Exception as e:
        logger.error(f"Batch processing failed: {str(e)}")
        raise

async def _filter_conflicting_unknowns(db: AsyncSession, unknown_entries: List[Dict]) -> None:
    """Filter out unknowns that conflict with existing known entries"""
    companies = {e["company"] for e in unknown_entries}
    
    result = await db.execute(
        select(JobApplication.company)
        .where(
            JobApplication.user_email == unknown_entries[0]["user_email"],
            JobApplication.company.in_(companies),
            JobApplication.job_title != DB_CONFIG["unknown_placeholder"]
        )
    )
    existing_companies = {r[0] for r in result.all()}
    
    # Remove entries with existing known positions
    unknown_entries[:] = [
        e for e in unknown_entries
        if e["company"] not in existing_companies
    ]

async def _execute_batch_insert(db: AsyncSession, batch: List[Dict]) -> int:
    """Execute the actual batch insert"""
    try:
        stmt = (
            pg_insert(JobApplication)
            .values(batch)
            .on_conflict_do_nothing(
                constraint="uix_user_company_job"
            )
        )
        result = await db.execute(stmt)
        return result.rowcount
    
    except Exception as e:
        logger.error(f"Batch insert failed: {str(e)}")
        await db.rollback()
        return 0