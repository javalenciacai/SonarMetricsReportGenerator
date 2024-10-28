from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime
import logging

class SchedulerService:
    def __init__(self):
        self.scheduler = BackgroundScheduler()
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)

    def start(self):
        """Start the scheduler"""
        if not self.scheduler.running:
            self.scheduler.start()
            self.logger.info("Scheduler started successfully")

    def stop(self):
        """Stop the scheduler"""
        if self.scheduler.running:
            self.scheduler.shutdown()
            self.logger.info("Scheduler stopped")

    def schedule_daily_report(self, job_func, hour=0, minute=0):
        """Schedule a daily report job"""
        trigger = CronTrigger(hour=hour, minute=minute)
        self.scheduler.add_job(
            job_func,
            trigger=trigger,
            id='daily_report',
            name='Generate Daily Report',
            replace_existing=True
        )
        self.logger.info(f"Daily report scheduled for {hour:02d}:{minute:02d}")

    def schedule_weekly_report(self, job_func, day_of_week=0, hour=0, minute=0):
        """Schedule a weekly report job"""
        trigger = CronTrigger(day_of_week=day_of_week, hour=hour, minute=minute)
        self.scheduler.add_job(
            job_func,
            trigger=trigger,
            id='weekly_report',
            name='Generate Weekly Report',
            replace_existing=True
        )
        self.logger.info(f"Weekly report scheduled for day {day_of_week} at {hour:02d}:{minute:02d}")

    def schedule_metric_checks(self, job_func, interval_hours=4):
        """Schedule metric change checks at regular intervals"""
        trigger = IntervalTrigger(hours=interval_hours)
        self.scheduler.add_job(
            job_func,
            trigger=trigger,
            id='metric_checks',
            name='Check Metric Changes',
            replace_existing=True
        )
        self.logger.info(f"Metric checks scheduled every {interval_hours} hours")
