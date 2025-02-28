import logging
from backend.database import SessionLocal
from backend.emails import get_gmail_service, fetch_and_classify_emails
from backend.logic import insert_job_applications  # <-- import the new function
import pytz
import datetime
from fastapi import APIRouter

logger = logging.getLogger(__name__)
router = APIRouter()

def daily_email_fetch_job():
    try:
        print("⚡ Running daily email fetch job NOW!")
        db = SessionLocal()

        # ✅ Force a debug print to confirm this line runs
        print("✅ Successfully connected to DB, now getting current time")

        current_time = datetime.datetime.now(pytz.utc)

        # ✅ Print timestamp to confirm execution
        print(f"🕒 Current UTC Time: {current_time.strftime('%Y-%m-%d %H:%M:%S')}")

        logger.info(f"🔄 Running daily email fetch job...")

        # ✅ Debugging Gmail service connection
        try:
            service = get_gmail_service()
            print("✅ Successfully initialized Gmail service")
        except Exception as e:
            print(f"❌ Failed to initialize Gmail service: {e}")
            raise e

        confirmations, _ = fetch_and_classify_emails(service)

        # ✅ Check if confirmations were fetched
        print(f"✅ Confirmations fetched: {len(confirmations)}")

        if confirmations:
            processed_count, skipped_count = insert_job_applications(db, confirmations)
            print(f"✅ Processed {processed_count} confirmations. Skipped {skipped_count}.")
        else:
            print("ℹ️ No confirmation emails found today.")

    except Exception as e:
        print(f"❌ Error in daily email fetch job: {e}")
        logger.error(f"❌ Error in daily email fetch: {e}")

    finally:
        print("✅ Closing database connection")
        db.close()


# ✅ New Route: Trigger Job via Render Cron Job
@router.get("/cron-trigger")
def cron_trigger():
    print("✅ Cron job triggered successfully!")
    daily_email_fetch_job()  # ✅ Run the job when Render hits this endpoint
    return {"message": "Job triggered via Render Cron"}
