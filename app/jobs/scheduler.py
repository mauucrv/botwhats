"""
APScheduler configuration and job registration.
"""

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.config import settings

logger = structlog.get_logger(__name__)

# Global scheduler instance
scheduler: AsyncIOScheduler = None


def init_scheduler() -> AsyncIOScheduler:
    """
    Initialize and configure the scheduler with all jobs.

    Returns:
        The configured scheduler instance
    """
    global scheduler

    scheduler = AsyncIOScheduler(timezone=settings.calendar_timezone)

    # Import job functions here to avoid circular imports
    from app.jobs.reminders import send_appointment_reminders
    from app.jobs.reports import send_weekly_report
    from app.jobs.backup import backup_database
    from app.jobs.sync_calendar import sync_calendar_events

    # Job 1: Daily appointment reminders
    # Sends reminders for appointments scheduled for the next day
    scheduler.add_job(
        send_appointment_reminders,
        trigger=CronTrigger(
            hour=settings.daily_reminder_hour,
            minute=settings.daily_reminder_minute,
        ),
        id="daily_reminders",
        name="Send daily appointment reminders",
        replace_existing=True,
    )
    logger.info(
        "Scheduled daily reminders",
        hour=settings.daily_reminder_hour,
        minute=settings.daily_reminder_minute,
    )

    # Job 2: Weekly statistics report
    # Sends a summary of the week's activity to the owner
    scheduler.add_job(
        send_weekly_report,
        trigger=CronTrigger(
            day_of_week=settings.weekly_report_day,
            hour=settings.weekly_report_hour,
            minute=settings.weekly_report_minute,
        ),
        id="weekly_report",
        name="Send weekly statistics report",
        replace_existing=True,
    )
    logger.info(
        "Scheduled weekly report",
        day=settings.weekly_report_day,
        hour=settings.weekly_report_hour,
    )

    # Job 3: Daily database backup
    # Creates a backup of the PostgreSQL database and uploads to Google Drive
    scheduler.add_job(
        backup_database,
        trigger=CronTrigger(
            hour=settings.daily_backup_hour,
            minute=settings.daily_backup_minute,
        ),
        id="daily_backup",
        name="Daily database backup",
        replace_existing=True,
    )
    logger.info(
        "Scheduled daily backup",
        hour=settings.daily_backup_hour,
        minute=settings.daily_backup_minute,
    )

    # Job 4: Calendar sync
    # Synchronizes Google Calendar events with the database
    scheduler.add_job(
        sync_calendar_events,
        trigger=IntervalTrigger(minutes=settings.calendar_sync_interval_minutes),
        id="calendar_sync",
        name="Sync Google Calendar events",
        replace_existing=True,
    )
    logger.info(
        "Scheduled calendar sync",
        interval_minutes=settings.calendar_sync_interval_minutes,
    )

    # Start the scheduler
    scheduler.start()
    logger.info("Scheduler started with all jobs")

    return scheduler


def shutdown_scheduler() -> None:
    """Shutdown the scheduler gracefully."""
    global scheduler

    if scheduler and scheduler.running:
        scheduler.shutdown(wait=True)
        logger.info("Scheduler shutdown complete")


def get_scheduler() -> AsyncIOScheduler:
    """Get the scheduler instance."""
    global scheduler
    return scheduler
