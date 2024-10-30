from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED, EVENT_JOB_MISSED
from datetime import datetime, timezone
import logging
import json

class SchedulerService:
    def __init__(self):
        self.scheduler = BackgroundScheduler(timezone='UTC')
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        self.job_registry = {}
        
        # Add listeners for job events
        self.scheduler.add_listener(
            self._handle_job_event,
            EVENT_JOB_ERROR | EVENT_JOB_EXECUTED | EVENT_JOB_MISSED
        )
        self.logger.info("Scheduler service initialized with UTC timezone")
        self.verify_scheduler_state()

    def _handle_job_event(self, event):
        """Handle job execution events with enhanced logging and status tracking"""
        job_id = event.job_id
        job_info = self.job_registry.get(job_id, {})
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

        try:
            if event.exception:
                self.logger.error(f"[{timestamp}] Job {job_id} failed: {str(event.exception)}")
                self.logger.error(f"Job details: Type: {job_info.get('type')}, "
                             f"Entity: {job_info.get('entity_type')} {job_info.get('entity_id')}")

                # Update job status with detailed error information
                self.job_registry[job_id] = {
                    **job_info,
                    'last_status': 'failed',
                    'last_error': str(event.exception),
                    'last_run': timestamp,
                    'error_count': job_info.get('error_count', 0) + 1,
                    'last_execution_details': {
                        'timestamp': timestamp,
                        'status': 'failed',
                        'error': str(event.exception),
                        'traceback': event.traceback if hasattr(event, 'traceback') else None
                    }
                }

                # Handle job retry logic
                if job_info.get('error_count', 0) < 3:  # Limit retries
                    retry_interval = job_info.get('interval', 3600) // 2  # Retry at half the normal interval
                    self.logger.info(f"[{timestamp}] Scheduling retry for job {job_id} in {retry_interval} seconds")
                    try:
                        self.schedule_metrics_update(
                            event.job.func,
                            job_info['entity_type'],
                            job_info['entity_id'],
                            retry_interval,
                            is_retry=True
                        )
                    except Exception as e:
                        self.logger.error(f"[{timestamp}] Failed to schedule retry for job {job_id}: {str(e)}")
                else:
                    self.logger.error(f"[{timestamp}] Job {job_id} exceeded retry limit (3 attempts)")

            elif event.code == EVENT_JOB_MISSED:
                self.logger.warning(f"[{timestamp}] Job {job_id} missed scheduled execution")
                self.job_registry[job_id] = {
                    **job_info,
                    'last_status': 'missed',
                    'last_run': timestamp,
                    'missed_runs': job_info.get('missed_runs', 0) + 1
                }

            else:  # Successful execution
                if hasattr(event, 'retval'):
                    success, execution_details = event.retval
                else:
                    success, execution_details = True, {}

                status = 'success' if success else 'failed'
                self.logger.info(f"[{timestamp}] Job {job_id} executed with status: {status}")

                # Update job registry with execution details
                self.job_registry[job_id] = {
                    **job_info,
                    'last_status': status,
                    'last_run': timestamp,
                    'last_error': None if success else execution_details.get('errors', []),
                    'successful_runs': job_info.get('successful_runs', 0) + (1 if success else 0),
                    'error_count': 0 if success else job_info.get('error_count', 0) + 1,
                    'last_execution_details': {
                        'timestamp': timestamp,
                        'status': status,
                        'metrics_summary': execution_details
                    }
                }

                # Verify next execution
                job = self.scheduler.get_job(job_id)
                if job and job.next_run_time:
                    self.logger.info(f"[{timestamp}] Next execution for {job_id} scheduled at: "
                                f"{job.next_run_time.strftime('%Y-%m-%d %H:%M:%S')} UTC")
                else:
                    self.logger.warning(f"[{timestamp}] Job {job_id} has no next execution time scheduled")

        except Exception as e:
            self.logger.error(f"[{timestamp}] Error handling job event: {str(e)}")
            self.job_registry[job_id] = {
                **job_info,
                'last_status': 'error',
                'last_error': str(e),
                'last_run': timestamp
            }

    def verify_scheduler_state(self):
        """Verify scheduler state and log active jobs"""
        try:
            active_jobs = self.scheduler.get_jobs()
            self.logger.info(f"Current scheduler state - Active jobs: {len(active_jobs)}")
            for job in active_jobs:
                next_run = job.next_run_time.strftime("%Y-%m-%d %H:%M:%S UTC") if job.next_run_time else "Not scheduled"
                job_status = self.get_job_status(job.id)
                self.logger.info(
                    f"Job ID: {job.id}, Next run: {next_run}, "
                    f"Status: {job_status.get('last_status') if job_status else 'unknown'}"
                )
            return True
        except Exception as e:
            self.logger.error(f"Error verifying scheduler state: {str(e)}")
            return False

    def start(self):
        """Start the scheduler"""
        try:
            if not self.scheduler.running:
                self.scheduler.start()
                self.logger.info("Scheduler started successfully (UTC)")
                self.verify_scheduler_state()
            return True
        except Exception as e:
            self.logger.error(f"Failed to start scheduler: {str(e)}")
            return False

    def schedule_metrics_update(self, job_func, entity_type, entity_id, interval_seconds, is_retry=False):
        """Schedule a metrics update job"""
        job_id = f"metrics_update_{entity_type}_{entity_id}"
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        
        try:
            # Remove existing job if it exists
            if not is_retry and job_id in self.job_registry:
                self.logger.debug(f"[{timestamp}] Removing existing job: {job_id}")
                self.scheduler.remove_job(job_id)
            
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
                'missed_runs': 0,
                'last_status': 'scheduled',
                'last_run': None,
                'last_error': None,
                'is_retry': is_retry
            }
            
            self.logger.info(
                f"[{timestamp}] {'Retry scheduled' if is_retry else 'Scheduled'} "
                f"metrics update for {entity_type} {entity_id} "
                f"every {interval_seconds} seconds"
            )
            
            # Verify job registration
            job = self.scheduler.get_job(job_id)
            if not job:
                raise Exception("Job verification failed - Job not properly registered")
            
            self.verify_scheduler_state()
            return True
            
        except Exception as e:
            self.logger.error(f"[{timestamp}] Failed to schedule metrics update job: {str(e)}")
            raise

    def get_job_status(self, job_id):
        """Get detailed status of a specific job"""
        status = self.job_registry.get(job_id, {})
        if status:
            job = self.scheduler.get_job(job_id)
            if job:
                status['next_run'] = job.next_run_time.strftime("%Y-%m-%d %H:%M:%S UTC") if job.next_run_time else None
        return status

    def get_all_job_statuses(self):
        """Get status of all registered jobs"""
        return {
            job_id: {
                **status,
                'next_run': self.scheduler.get_job(job_id).next_run_time.strftime("%Y-%m-%d %H:%M:%S UTC")
                if self.scheduler.get_job(job_id) and self.scheduler.get_job(job_id).next_run_time
                else None
            }
            for job_id, status in self.job_registry.items()
        }
