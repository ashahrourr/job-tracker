import logging
from backend.database import SessionLocal, TokenStore
from backend.emails import get_gmail_service, fetch_and_classify_emails
from backend.logic import insert_job_applications
from fastapi import APIRouter, Depends, HTTPException
from backend.session import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()

def process_user_emails(user_email: str):
    """
    Process emails for a single user.
    """
    db = SessionLocal()
    try:
        service = get_gmail_service(user_email)
        confirmations, rejections = fetch_and_classify_emails(service)

        processed_count, skipped_count = insert_job_applications(db, confirmations, user_email)
        logger.info(f"✅ User {user_email}: Processed {processed_count} applications, skipped {skipped_count}.")
        
    except Exception as e:
        logger.error(f"❌ Error processing emails for {user_email}: {e}")
    finally:
        db.close()

def scheduled_email_fetch():
    """
    Processes emails for all users. This function will be triggered externally by cron-job.org.
    """
    logger.info("⏳ Running scheduled email fetch job...")
    db = SessionLocal()
    
    users = db.query(TokenStore).all()
    for user in users:
        process_user_emails(user.user_id)

    db.close()
    logger.info("✅ Scheduled email fetch completed.")

@router.get("/trigger-email-fetch")
def trigger_email_fetch():
    """
    Public endpoint that cron-job.org will call to trigger the email fetch job.
    """
    try:
        scheduled_email_fetch()
        return {"message": "Email fetch triggered successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/my-email-fetch")
def my_email_fetch(current_user: str = Depends(get_current_user)):
    """
    JWT-protected endpoint for the logged-in user to fetch and process their own emails manually.
    """
    try:
        results = process_user_emails(current_user)
        return {
            "message": f"Processed emails for {current_user}.",
            "details": results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
