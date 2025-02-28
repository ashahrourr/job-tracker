# backend/scheduler.py
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import logging
from backend.database import SessionLocal
from backend.emails import get_gmail_service, fetch_and_classify_emails
from backend.logic import insert_job_applications  # <-- import the new function
import pytz
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
import datetime
import threading

logger = logging.getLogger(__name__)
scheduler = BackgroundScheduler(timezone=pytz.utc)

def schedule_daily_fetch():
    print("inside daily fetch")
    trigger = IntervalTrigger(seconds=120)  
    scheduler.add_job(
        func=daily_email_fetch_job, 
        trigger=trigger,
        id="daily_email_fetch",
        replace_existing=True
    )
    print(f"📌 Scheduled jobs: {scheduler.get_jobs()}")

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


