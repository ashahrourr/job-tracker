import datetime
from sqlalchemy.dialects.postgresql import insert as pg_insert
from backend.workflow_pipeline.database import JobApplication, AsyncSession
from typing import List, Dict
import select

async def insert_job_applications(
    db: AsyncSession, 
    applications: List[Dict[str, str]],
    user_email: str
) -> tuple[int, int]:
    if not applications:
        return 0, 0

    # Step 1: Deduplicate within the batch (prefer known titles)
    company_map = {}
    for app in applications:
        raw_company = app.get("company", "").strip()
        raw_title = app.get("job_title", "").strip()

        if not raw_company:
            continue

        company = raw_company.lower()
        job_title = raw_title.lower() if raw_title else "unknown position"

        # Keep the entry with the highest priority (known > unknown)
        if company not in company_map or (
            company_map[company]["job_title"] == "unknown position" 
            and job_title != "unknown position"
        ):
            company_map[company] = {
                "user_email": user_email,
                "company": company,
                "job_title": job_title,
                "applied_date": datetime.datetime.utcnow()
            }

    valid_batch = list(company_map.values())

    # Step 2: Separate known and unknown entries
    known_entries = [
        entry for entry in valid_batch 
        if entry["job_title"] != "unknown position"
    ]
    unknown_entries = [
        entry for entry in valid_batch 
        if entry["job_title"] == "unknown position"
    ]

    # Step 3: Check database for existing known titles in unknown entries
    if unknown_entries:
        unknown_companies = {entry["company"] for entry in unknown_entries}
        # Query companies where user already has a known title
        query = (
            select(JobApplication.company)
            .where(
                JobApplication.user_email == user_email,
                JobApplication.company.in_(unknown_companies),
                JobApplication.job_title != "unknown position"
            )
        )
        result = await db.execute(query)
        existing_known_companies = {row.company for row in result.scalars()}
        # Filter out unknowns that conflict with known titles in DB
        filtered_unknowns = [
            entry for entry in unknown_entries
            if entry["company"] not in existing_known_companies
        ]
    else:
        filtered_unknowns = []

    # Final batch: known + filtered unknowns
    final_batch = known_entries + filtered_unknowns

    if not final_batch:
        return 0, 0

    # Step 4: Insert with conflict check (same as before)
    stmt = pg_insert(JobApplication.__table__).values(final_batch).on_conflict_do_nothing(
        constraint="uix_user_company_job"
    )
    result = await db.execute(stmt)
    await db.commit()

    processed = result.rowcount
    skipped = len(final_batch) - processed
    return processed, skipped