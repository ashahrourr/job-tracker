# scheduler.py
import logging
from sqlalchemy import select
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from backend.workflow_pipeline.database import SessionLocal, TokenStore
from backend.workflow_pipeline.emails import get_gmail_service, fetch_and_classify_emails
from backend.workflow_pipeline.logic import insert_job_applications
from backend.workflow_pipeline.session import get_current_user
from .celery_app import app  # ✅ From separate file

logger = logging.getLogger(__name__)
router = APIRouter()

# ------ Celery Tasks (Synchronous) ------
@app.task
def process_user_emails_task(user_email: str):
    import asyncio
    asyncio.run(async_process_user_emails(user_email))

# ------ Async Processing Logic ------
async def async_process_user_emails(user_email: str):
    db = SessionLocal()
    try:
        service = await get_gmail_service(user_email)
        confirmations, _ = await fetch_and_classify_emails(service)
        await insert_job_applications(db, confirmations, user_email)
    finally:
        await db.close()

# ------ Scheduled Job ------
async def scheduled_email_fetch():
    db = SessionLocal()
    try:
        result = await db.execute(select(TokenStore.user_id))
        for user in result.scalars().all():
            process_user_emails_task.delay(user)  # Enqueue Celery task
    finally:
        await db.close()

# ------ Endpoints ------
@router.get("/trigger-email-fetch")
async def trigger_email_fetch():
    try:
        await scheduled_email_fetch()
        return {"message": "Email fetch triggered."}
    except Exception as e:
        raise HTTPException(500, detail=str(e))

@router.get("/my-email-fetch")
async def my_email_fetch(current_user: str = Depends(get_current_user)):
    try:
        await async_process_user_emails(current_user)
        return {"message": f"Processed emails for {current_user}."}
    except Exception as e:
        raise HTTPException(500, detail=str(e))