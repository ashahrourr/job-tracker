# scheduler.py
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import logging
from database import SessionLocal
from emails import get_gmail_service, fetch_and_classify_emails
from main import process_emails_logic

# Set up logging
logger = logging.getLogger(__name__)

# Initialize the background scheduler
scheduler = BackgroundScheduler()

def schedule_daily_fetch():
    """
    Schedules the daily email fetch job to run at 23:59 (11:59 PM).
    """
    trigger = CronTrigger(hour=23, minute=59)  # Runs at 11:59 PM daily

    scheduler.add_job(
        func=daily_email_fetch_job, 
        trigger=trigger,
        id="daily_email_fetch",
        replace_existing=True
    )

def daily_email_fetch_job():
    """
    Fetches and processes today's job confirmation emails at the end of the day.
    """
    db = SessionLocal()
    try:
        logger.info("🔄 Running daily email fetch job...")

        # 1. Initialize Gmail service
        service = get_gmail_service()

        # 2. Fetch all job confirmation emails from today
        confirmations, _ = fetch_and_classify_emails(service)

        # 3. Process and insert into DB
        if confirmations:
            process_emails_logic(db, confirmations)
            db.commit()
            logger.info(f"✅ Processed {len(confirmations)} job confirmations.")
        else:
            logger.info("ℹ️ No confirmation emails found today.")

    except Exception as e:
        logger.error(f"❌ Error in daily email fetch: {str(e)}")
    finally:
        db.close()

def start_scheduler():
    """
    Starts the APScheduler background scheduler.
    """
    scheduler.start()
    schedule_daily_fetch()
    logger.info("✅ Scheduler started and job scheduled.")
