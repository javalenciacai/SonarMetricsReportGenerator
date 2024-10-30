from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED
from datetime import datetime
import logging

class SchedulerService:
    def __init__(self):
        self.scheduler = BackgroundScheduler()
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        self.job_registry = {}
        
        # Add error listener
        self.scheduler.add_listener(self._handle_job_event, 
                                  EVENT_JOB_ERROR | EVENT_JOB_EXECUTED)

    def _handle_job_event(self, event):
        """Handle job execution events"""
        if event.exception:
            self.logger.error(f"Job {event.job_id} failed: {str(event.exception)}")
            if event.job_id in self.job_registry:
                job_info = self.job_registry[event.job_id]
                self.logger.info(f"Attempting to reschedule failed job: {event.job_id}")
                try:
                    # Retry scheduling with the same parameters
                    self.schedule_metrics_update(
                        event.job.func,
                        job_info['entity_type'],
                        job_info['entity_id'],
                        job_info['interval']
                    )
                except Exception as e:
                    self.logger.error(f"Failed to reschedule job {event.job_id}: {str(e)}")
        else:
            self.logger.info(f"Job {event.job_id} executed successfully")

    def start(self):
        """Start the scheduler with error handling"""
        try:
            if not self.scheduler.running:
                self.scheduler.start()
                self.logger.info("Scheduler started successfully")
                return True
            return True
        except Exception as e:
            self.logger.error(f"Failed to start scheduler: {str(e)}")
            return False

    def stop(self):
        """Stop the scheduler safely"""
        try:
            if self.scheduler.running:
                self.scheduler.shutdown()
                self.logger.info("Scheduler stopped")
                return True
            return True
        except Exception as e:
            self.logger.error(f"Failed to stop scheduler: {str(e)}")
            return False

    def schedule_metrics_update(self, job_func, entity_type, entity_id, interval_seconds):
        """Schedule a metrics update job with improved error handling"""
        job_id = f"metrics_update_{entity_type}_{entity_id}"
        
        try:
            # Remove existing job if it exists
            if job_id in self.job_registry:
                self.scheduler.remove_job(job_id)
                self.logger.info(f"Removed existing job: {job_id}")
            
            trigger = IntervalTrigger(seconds=interval_seconds)
            self.scheduler.add_job(
                job_func,
                trigger=trigger,
                id=job_id,
                name=f'Update Metrics for {entity_type} {entity_id}',
                replace_existing=True,
                args=[entity_type, entity_id],
                max_instances=1
            )
            
            self.job_registry[job_id] = {
                'type': 'metrics_update',
                'entity_type': entity_type,
                'entity_id': entity_id,
                'interval': interval_seconds,
                'last_scheduled': datetime.now()
            }
            
            self.logger.info(f"Successfully scheduled metrics update for {entity_type} {entity_id} "
                           f"every {interval_seconds} seconds")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to schedule metrics update job: {str(e)}")
            raise

    def update_metrics_interval(self, entity_type, entity_id, new_interval):
        """Update the interval for an existing metrics update job"""
        job_id = f"metrics_update_{entity_type}_{entity_id}"
        try:
            if job_id in self.job_registry:
                job = self.scheduler.get_job(job_id)
                if job:
                    self.schedule_metrics_update(
                        job.func,
                        entity_type,
                        entity_id,
                        new_interval
                    )
                    self.logger.info(f"Updated metrics interval for {entity_type} {entity_id} "
                                   f"to {new_interval} seconds")
                    return True
            return False
        except Exception as e:
            self.logger.error(f"Failed to update metrics interval: {str(e)}")
            return False

    def schedule_daily_report(self, job_func, hour=0, minute=0):
        """Schedule a daily report job"""
        try:
            trigger = CronTrigger(hour=hour, minute=minute)
            self.scheduler.add_job(
                job_func,
                trigger=trigger,
                id='daily_report',
                name='Generate Daily Report',
                replace_existing=True,
                max_instances=1
            )
            self.logger.info(f"Daily report scheduled for {hour:02d}:{minute:02d}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to schedule daily report: {str(e)}")
            return False

    def schedule_weekly_report(self, job_func, day_of_week=0, hour=0, minute=0):
        """Schedule a weekly report job"""
        try:
            trigger = CronTrigger(day_of_week=day_of_week, hour=hour, minute=minute)
            self.scheduler.add_job(
                job_func,
                trigger=trigger,
                id='weekly_report',
                name='Generate Weekly Report',
                replace_existing=True,
                max_instances=1
            )
            self.logger.info(f"Weekly report scheduled for day {day_of_week} at {hour:02d}:{minute:02d}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to schedule weekly report: {str(e)}")
            return False

    def schedule_metric_checks(self, job_func, interval_hours=4):
        """Schedule metric change checks at regular intervals"""
        try:
            trigger = IntervalTrigger(hours=interval_hours)
            self.scheduler.add_job(
                job_func,
                trigger=trigger,
                id='metric_checks',
                name='Check Metric Changes',
                replace_existing=True,
                max_instances=1
            )
            self.logger.info(f"Metric checks scheduled every {interval_hours} hours")
            return True
        except Exception as e:
            self.logger.error(f"Failed to schedule metric checks: {str(e)}")
            return False

    def remove_metrics_update_job(self, entity_type, entity_id):
        """Remove a metrics update job"""
        job_id = f"metrics_update_{entity_type}_{entity_id}"
        try:
            if job_id in self.job_registry:
                self.scheduler.remove_job(job_id)
                del self.job_registry[job_id]
                self.logger.info(f"Removed metrics update job for {entity_type} {entity_id}")
                return True
            return False
        except Exception as e:
            self.logger.error(f"Failed to remove metrics update job: {str(e)}")
            return False
