# backend/scheduler.py
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import logging
from backend.database import SessionLocal
from backend.emails import get_gmail_service, fetch_and_classify_emails
from backend.logic import insert_job_applications  # <-- import the new function
import pytz
from apscheduler.triggers.interval import IntervalTrigger
import datetime

logger = logging.getLogger(__name__)
scheduler = BackgroundScheduler()

def schedule_daily_fetch():
    print("inside daily fetch")
    trigger = IntervalTrigger(seconds=120) 
    scheduler.add_job(
        func=daily_email_fetch_job, 
        trigger=trigger,
        id="daily_email_fetch",
        replace_existing=True
    )

def daily_email_fetch_job():
    print("daily email fetch job called")
    db = SessionLocal()
    try:
        current_time = datetime.now(pytz.utc)
        logger.info(f"🕒 Current UTC Time: {current_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("🔄 Running daily email fetch job...")

        service = get_gmail_service()
        confirmations, _ = fetch_and_classify_emails(service)

        if confirmations:
            processed_count, skipped_count = insert_job_applications(db, confirmations)
            logger.info(f"✅ Processed {processed_count} confirmations. Skipped {skipped_count}.")
        else:
            logger.info("ℹ️ No confirmation emails found today.")

    except Exception as e:
        logger.error(f"❌ Error in daily email fetch: {str(e)}")
    finally:
        db.close()

def start_scheduler():
    print("inside stat scheduler")
    scheduler.start()
    schedule_daily_fetch()
    print("called daily fetch")
