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
import threading

logger = logging.getLogger(__name__)
scheduler = BackgroundScheduler(timezone=pytz.utc)

def schedule_daily_fetch():
    print("inside daily fetch")
    trigger = IntervalTrigger(seconds=120) 
    job = scheduler.add_job(
        func=daily_email_fetch_job, 
        trigger=trigger,
        id="daily_email_fetch",
        replace_existing=True
    )
    print(f"📌 Scheduled jobs: {scheduler.get_jobs()}")
    print(f"🕒 Next run time: {job.next_run_time}")

def daily_email_fetch_job():
    try:
        print("⚡ Running daily email fetch job NOW!")
        db = SessionLocal()
        current_time = datetime.datetime.now(pytz.utc)
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
        print(f"❌ Error in daily email fetch job: {e}")
        logger.error(f"❌ Error in daily email fetch: {e}")
    finally:
        db.close()

def start_scheduler():
    print("🚀 Inside start scheduler")

    def run():
        scheduler.start()

    if not scheduler.running:
        print("✅ Starting scheduler in a thread...")
        thread = threading.Thread(target=run, daemon=True)
        thread.start()
    else:
        print("⚠️ Scheduler already running.")

    schedule_daily_fetch()
    print(f"📌 Jobs after scheduling: {scheduler.get_jobs()}")


