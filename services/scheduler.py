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
        self.verify_scheduler_state()

    def verify_scheduler_state(self):
        """Verify scheduler state and log active jobs"""
        try:
            active_jobs = self.scheduler.get_jobs()
            self.logger.info(f"Current scheduler state - Active jobs: {len(active_jobs)}")
            for job in active_jobs:
                next_run = job.next_run_time.strftime("%Y-%m-%d %H:%M:%S") if job.next_run_time else "Not scheduled"
                self.logger.info(f"Job ID: {job.id}, Next run: {next_run}, "
                               f"Function: {job.func.__name__}")
            return True
        except Exception as e:
            self.logger.error(f"Error verifying scheduler state: {str(e)}")
            return False

    def _handle_job_event(self, event):
        """Handle job execution events with enhanced logging and verification"""
        job_id = event.job_id
        job_info = self.job_registry.get(job_id, {})
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if event.exception:
            self.logger.error(f"[{timestamp}] Job {job_id} failed: {str(event.exception)}")
            self.logger.error(f"Job details: Type: {job_info.get('type')}, "
                          f"Entity: {job_info.get('entity_type')} {job_info.get('entity_id')}")

            if job_id in self.job_registry:
                self.logger.info(f"[{timestamp}] Attempting to reschedule failed job: {job_id}")
                try:
                    # Update job status in registry
                    self.job_registry[job_id].update({
                        'last_status': 'failed',
                        'last_error': str(event.exception),
                        'last_run': timestamp,
                        'error_count': self.job_registry[job_id].get('error_count', 0) + 1
                    })

                    # Retry scheduling with the same parameters
                    if self.job_registry[job_id].get('error_count', 0) <= 3:  # Limit retries
                        self.schedule_metrics_update(
                            event.job.func,
                            job_info['entity_type'],
                            job_info['entity_id'],
                            job_info['interval']
                        )
                    else:
                        self.logger.error(f"[{timestamp}] Job {job_id} exceeded retry limit (3 attempts)")
                except Exception as e:
                    self.logger.error(f"[{timestamp}] Failed to reschedule job {job_id}: {str(e)}")
                    self.job_registry[job_id]['reschedule_error'] = str(e)
        else:
            self.logger.info(f"[{timestamp}] Job {job_id} executed successfully")
            self.logger.debug(f"Job details - Type: {job_info.get('type', 'unknown')}, "
                          f"Entity: {job_info.get('entity_type', 'unknown')} {job_info.get('entity_id', 'unknown')}, "
                          f"Interval: {job_info.get('interval', 'unknown')}s")

            if job_id in self.job_registry:
                # Update job status in registry with execution metrics
                self.job_registry[job_id].update({
                    'last_status': 'success',
                    'last_run': timestamp,
                    'last_error': None,
                    'successful_runs': self.job_registry[job_id].get('successful_runs', 0) + 1,
                    'error_count': 0  # Reset error count on successful execution
                })

                # Verify next execution time
                job = self.scheduler.get_job(job_id)
                if job and job.next_run_time:
                    self.logger.info(f"[{timestamp}] Next execution for {job_id} scheduled at: "
                                 f"{job.next_run_time.strftime('%Y-%m-%d %H:%M:%S')}")
                else:
                    self.logger.warning(f"[{timestamp}] Job {job_id} has no next execution time scheduled")

    def start(self):
        """Start the scheduler with enhanced error handling and state verification"""
        try:
            if not self.scheduler.running:
                self.scheduler.start()
                self.logger.info("Scheduler started successfully")
                if self.verify_scheduler_state():
                    self.logger.info("Scheduler state verification completed successfully")
                return True
            return True
        except Exception as e:
            self.logger.error(f"Failed to start scheduler: {str(e)}")
            return False

    def schedule_metrics_update(self, job_func, entity_type, entity_id, interval_seconds):
        """Schedule a metrics update job with enhanced logging and verification"""
        job_id = f"metrics_update_{entity_type}_{entity_id}"
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        try:
            # Remove existing job if it exists
            if job_id in self.job_registry:
                self.logger.debug(f"[{timestamp}] Removing existing job: {job_id}")
                self.scheduler.remove_job(job_id)
                self.logger.info(f"[{timestamp}] Removed existing job: {job_id}")
            
            self.logger.debug(f"[{timestamp}] Scheduling new job: {job_id} with interval {interval_seconds}s")
            trigger = IntervalTrigger(seconds=interval_seconds)
            
            # Add the job with detailed metadata
            self.scheduler.add_job(
                job_func,
                trigger=trigger,
                id=job_id,
                name=f'Update Metrics for {entity_type} {entity_id}',
                replace_existing=True,
                args=[entity_type, entity_id],
                max_instances=1
            )
            
            # Update job registry with detailed status information
            self.job_registry[job_id] = {
                'type': 'metrics_update',
                'entity_type': entity_type,
                'entity_id': entity_id,
                'interval': interval_seconds,
                'created_at': timestamp,
                'last_scheduled': timestamp,
                'successful_runs': 0,
                'error_count': 0,
                'last_status': 'scheduled',
                'last_run': None,
                'last_error': None
            }
            
            self.logger.info(f"[{timestamp}] Successfully scheduled metrics update for {entity_type} {entity_id} "
                         f"every {interval_seconds} seconds")
            
            # Verify job registration and next execution
            job = self.scheduler.get_job(job_id)
            if job and job.next_run_time:
                self.logger.info(f"[{timestamp}] Job {job_id} verified - First execution scheduled for: "
                             f"{job.next_run_time.strftime('%Y-%m-%d %H:%M:%S')}")
            else:
                raise Exception("Job verification failed - Job not properly registered")
            
            # Log current scheduler state
            self.verify_scheduler_state()
            
            return True
            
        except Exception as e:
            self.logger.error(f"[{timestamp}] Failed to schedule metrics update job: {str(e)}")
            raise

    def get_job_status(self, job_id):
        """Get detailed status of a specific job"""
        return self.job_registry.get(job_id)

    def get_all_job_statuses(self):
        """Get status of all registered jobs"""
        return self.job_registry
