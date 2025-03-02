import logging
from backend.database import SessionLocal
from backend.emails import get_gmail_service, fetch_and_classify_emails, save_confirmations_to_json, save_rejections_to_json
from backend.logic import insert_job_applications  # <-- import the new function
import pytz
import datetime
from fastapi import APIRouter

logger = logging.getLogger(__name__)
router = APIRouter()

def daily_email_fetch_job():
    try:
        db = SessionLocal()

        try:
            service = get_gmail_service()
        except Exception as e:
            logger.error(f"Failed to initialize Gmail service: {e}")
            raise e

        confirmations, rejections = fetch_and_classify_emails(service)

        if confirmations:
            save_confirmations_to_json(confirmations, "job_conformation_emails.json")

            processed_count, skipped_count = insert_job_applications(db, confirmations)
        else:
            logger.info("ℹ️ No confirmation emails found today.")

        if rejections:
            save_rejections_to_json(rejections, "job_rejection_emails.json")
        else:
            logger.info("ℹ️ No rejection emails found today.")

    except Exception as e:
        logger.error(f"❌ Error in daily email fetch: {e}")

    finally:
        db.close()


# ✅ New Route: Trigger Job via Render Cron Job
@router.get("/cron-trigger")
def cron_trigger():
    daily_email_fetch_job()  # ✅ Run the job when Render hits this endpoint
    return {"message": "Job triggered via Cron org"}
