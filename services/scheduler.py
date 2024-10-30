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
        self.job_registry = {}

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

    def schedule_metrics_update(self, job_func, entity_type, entity_id, interval_seconds):
        """Schedule a metrics update job with custom interval"""
        job_id = f"metrics_update_{entity_type}_{entity_id}"
        
        # Remove existing job if it exists
        if job_id in self.job_registry:
            self.scheduler.remove_job(job_id)
        
        trigger = IntervalTrigger(seconds=interval_seconds)
        self.scheduler.add_job(
            job_func,
            trigger=trigger,
            id=job_id,
            name=f'Update Metrics for {entity_type} {entity_id}',
            replace_existing=True,
            args=[entity_type, entity_id]
        )
        self.job_registry[job_id] = {
            'type': 'metrics_update',
            'entity_type': entity_type,
            'entity_id': entity_id,
            'interval': interval_seconds
        }
        self.logger.info(f"Scheduled metrics update for {entity_type} {entity_id} every {interval_seconds} seconds")

    def update_metrics_interval(self, entity_type, entity_id, new_interval):
        """Update the interval for an existing metrics update job"""
        job_id = f"metrics_update_{entity_type}_{entity_id}"
        if job_id in self.job_registry:
            job_info = self.job_registry[job_id]
            self.schedule_metrics_update(
                self.scheduler.get_job(job_id).func,
                entity_type,
                entity_id,
                new_interval
            )
            self.logger.info(f"Updated metrics interval for {entity_type} {entity_id} to {new_interval} seconds")
            return True
        return False

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

    def remove_metrics_update_job(self, entity_type, entity_id):
        """Remove a metrics update job"""
        job_id = f"metrics_update_{entity_type}_{entity_id}"
        if job_id in self.job_registry:
            self.scheduler.remove_job(job_id)
            del self.job_registry[job_id]
            self.logger.info(f"Removed metrics update job for {entity_type} {entity_id}")
            return True
        return False
