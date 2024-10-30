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
        self.logger.info("Scheduler service initialized")

    def _handle_job_event(self, event):
        """Handle job execution events"""
        if event.exception:
            self.logger.error(f"Job {event.job_id} failed: {str(event.exception)}")
            self.logger.error(f"Job details: {event.job}")
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
            self.logger.info(f"Job {event.job_id} executed successfully at {datetime.now()}")
            if event.job_id in self.job_registry:
                job_info = self.job_registry[event.job_id]
                self.logger.debug(f"Job details - Type: {job_info['type']}, "
                               f"Entity: {job_info['entity_type']} {job_info['entity_id']}, "
                               f"Interval: {job_info['interval']}s")

    def start(self):
        """Start the scheduler with error handling"""
        try:
            if not self.scheduler.running:
                self.scheduler.start()
                self.logger.info("Scheduler started successfully")
                self.logger.debug(f"Active jobs: {len(self.scheduler.get_jobs())}")
                return True
            return True
        except Exception as e:
            self.logger.error(f"Failed to start scheduler: {str(e)}")
            return False

    def schedule_metrics_update(self, job_func, entity_type, entity_id, interval_seconds):
        """Schedule a metrics update job with improved error handling and logging"""
        job_id = f"metrics_update_{entity_type}_{entity_id}"
        
        try:
            # Remove existing job if it exists
            if job_id in self.job_registry:
                self.logger.debug(f"Removing existing job: {job_id}")
                self.scheduler.remove_job(job_id)
                self.logger.info(f"Removed existing job: {job_id}")
            
            self.logger.debug(f"Scheduling new job: {job_id} with interval {interval_seconds}s")
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
            self.logger.debug(f"Current active jobs: {len(self.scheduler.get_jobs())}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to schedule metrics update job: {str(e)}")
            raise

    # ... [rest of the methods remain the same]
