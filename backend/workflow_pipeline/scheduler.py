import logging
import asyncio
from sqlalchemy import select
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from backend.workflow_pipeline.database import SessionLocal, TokenStore
from backend.workflow_pipeline.emails import get_gmail_service, fetch_and_classify_emails
from backend.workflow_pipeline.logic import insert_job_applications
from backend.workflow_pipeline.session import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()

# ------ Async Processing Logic ------
async def async_process_user_emails(user_email: str):
    async with SessionLocal() as db:
        try:
            service = await get_gmail_service(user_email)
            if not service:
                logger.error(f"No Gmail service for {user_email}")
                return

            confirmations = await fetch_and_classify_emails(service)
            processed, skipped = await insert_job_applications(db, confirmations, user_email)
            logger.info(f"✅ Processed {processed} applications for {user_email}")
        except Exception as e:
            logger.error(f"❌ Error processing {user_email}: {str(e)}", exc_info=True)

# ------ Concurrent Scheduler ------
async def scheduled_email_fetch(max_concurrent_users: int = 5):
    async with SessionLocal() as db:
        result = await db.execute(select(TokenStore.user_id))
        users = result.scalars().all()

    semaphore = asyncio.Semaphore(max_concurrent_users)

    async def limited_worker(user_email: str):
        async with semaphore:
            await async_process_user_emails(user_email)

    logger.info(f"🚀 Starting email fetch for {len(users)} users...")
    await asyncio.gather(*[limited_worker(u) for u in users])
    logger.info(f"✅ Email fetch complete.")

# ------ Endpoints ------
@router.get("/trigger-email-fetch")
async def trigger_email_fetch():
    try:
        asyncio.create_task(scheduled_email_fetch())
        return {"message": "Email fetch started in background."}
    except Exception as e:
        raise HTTPException(500, detail=str(e))

@router.get("/my-email-fetch")
async def my_email_fetch(current_user: str = Depends(get_current_user)):
    try:
        await async_process_user_emails(current_user)
        return {"message": f"Processed emails for {current_user}."}
    except Exception as e:
        raise HTTPException(500, detail=str(e))