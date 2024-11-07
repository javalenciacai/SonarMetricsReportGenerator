import os
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED, EVENT_JOB_MISSED
from datetime import datetime, timezone
import logging
from services.report_generator import ReportGenerator
from database.schema import execute_query, get_update_preferences
from services.metrics_updater import update_entity_metrics
import json

class SchedulerService:
    def __init__(self):
        self.scheduler = BackgroundScheduler(timezone='UTC')
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        self.job_registry = {}
        self.report_generator = ReportGenerator()
        
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

                if job_info.get('error_count', 0) < 3:
                    retry_interval = 1800
                    self.logger.info(f"[{timestamp}] Scheduling retry for job {job_id} in {retry_interval} seconds")
                    try:
                        if job_info['type'] == 'report':
                            self.schedule_report(
                                job_info['report_type'],
                                job_info['frequency'],
                                job_info['recipients'],
                                job_info['report_format'],
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

            else:
                if hasattr(event, 'retval'):
                    success, execution_details = event.retval
                else:
                    success, execution_details = True, {}

                status = 'success' if success else 'failed'
                self.logger.info(f"[{timestamp}] Job {job_id} executed with status: {status}")

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
                        'report_summary': execution_details
                    }
                }

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

    def schedule_metrics_update(self, entity_type, entity_id, interval=3600):
        """Schedule metrics update for a specific entity (repository or group)"""
        try:
            job_id = f"update_{entity_type}_{entity_id}"
            
            if job_id in self.job_registry:
                self.scheduler.remove_job(job_id)
                self.logger.info(f"Removed existing job for {entity_type} {entity_id}")
            
            self.scheduler.add_job(
                func=lambda: update_entity_metrics(entity_type, entity_id),
                trigger=IntervalTrigger(seconds=interval, timezone='UTC'),
                id=job_id,
                name=f"Update {entity_type} {entity_id}",
                replace_existing=True
            )
            
            self.job_registry[job_id] = {
                'type': 'update',
                'entity_type': entity_type,
                'entity_id': entity_id,
                'interval': interval,
                'created_at': datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
            }
            
            self.logger.info(f"Successfully scheduled {entity_type} update job for {entity_id} with {interval}s interval")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to schedule {entity_type} update job for {entity_id}: {str(e)}")
            return False

    def initialize_update_intervals(self):
        """Initialize update intervals for all repositories from database"""
        query = """
        SELECT repo_key, update_interval
        FROM repositories
        WHERE is_active = true;
        """
        try:
            result = execute_query(query)
            if result:
                for repo_key, interval in result:
                    job_id = f"update_{repo_key}"
                    if interval > 0:
                        self.schedule_metrics_update('repository', repo_key, interval)
                        self.logger.info(f"Initialized update job for {repo_key} with {interval}s interval")
            return True
        except Exception as e:
            self.logger.error(f"Error initializing update intervals: {str(e)}")
            return False

    def start(self):
        """Start the scheduler with automatic interval initialization"""
        try:
            if not self.scheduler.running:
                self.scheduler.start()
                self.logger.info("Scheduler started successfully (UTC)")
                self.verify_scheduler_state()
                self._schedule_default_reports()
                self.initialize_update_intervals()
            return True
        except Exception as e:
            self.logger.error(f"Failed to start scheduler: {str(e)}")
            return False

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

    def get_job_status(self, job_id):
        """Get detailed status of a specific job"""
        return self.job_registry.get(job_id, None)

    def _schedule_default_reports(self):
        """Schedule default daily and weekly reports"""
        try:
            self.scheduler.add_job(
                self._generate_daily_report,
                CronTrigger(hour=1, minute=0, timezone='UTC'),
                id='daily_report',
                name='Daily Metrics Report',
                replace_existing=True
            )

            self.scheduler.add_job(
                self._generate_weekly_report,
                CronTrigger(day_of_week='mon', hour=2, minute=0, timezone='UTC'),
                id='weekly_report',
                name='Weekly Metrics Report',
                replace_existing=True
            )

            self.scheduler.add_job(
                self._check_metric_changes,
                IntervalTrigger(hours=4, timezone='UTC'),
                id='metric_alerts',
                name='Metric Change Alerts',
                replace_existing=True
            )

            self.logger.info("Default report schedules configured successfully")
        except Exception as e:
            self.logger.error(f"Error scheduling default reports: {str(e)}")

    def _generate_daily_report(self):
        """Generate and send daily report"""
        try:
            report = self.report_generator.generate_daily_report()
            if report:
                recipients = self._get_report_recipients('daily')
                if recipients:
                    success = self.report_generator.send_email(
                        recipients,
                        "Daily SonarCloud Metrics Report",
                        report,
                        'HTML'
                    )
                    return success, {"report_type": "daily", "recipients": len(recipients)}
            return False, {"error": "No report data generated"}
        except Exception as e:
            self.logger.error(f"Error generating daily report: {str(e)}")
            return False, {"error": str(e)}

    def _generate_weekly_report(self):
        """Generate and send weekly report"""
        try:
            report = self.report_generator.generate_weekly_report()
            if report:
                recipients = self._get_report_recipients('weekly')
                if recipients:
                    success = self.report_generator.send_email(
                        recipients,
                        "Weekly SonarCloud Metrics Report",
                        report,
                        'HTML'
                    )
                    return success, {"report_type": "weekly", "recipients": len(recipients)}
            return False, {"error": "No report data generated"}
        except Exception as e:
            self.logger.error(f"Error generating weekly report: {str(e)}")
            return False, {"error": str(e)}

    def _check_metric_changes(self):
        """Check for significant metric changes and send alerts"""
        try:
            alerts = self.report_generator.check_metric_changes()
            if alerts:
                recipients = self._get_report_recipients('alerts')
                if recipients:
                    success = self.report_generator.send_email(
                        recipients,
                        "SonarCloud Metric Change Alert",
                        alerts,
                        'HTML'
                    )
                    return success, {"alert_count": len(alerts)}
            return True, {"message": "No significant changes detected"}
        except Exception as e:
            self.logger.error(f"Error checking metric changes: {str(e)}")
            return False, {"error": str(e)}

    def _get_report_recipients(self, report_type):
        """Get recipients for a specific report type"""
        query = """
        SELECT recipients
        FROM report_schedules
        WHERE report_type = %s AND is_active = true;
        """
        try:
            result = execute_query(query, (report_type,))
            if result:
                recipients = set()
                for row in result:
                    if isinstance(row[0], str):
                        recipients.update(json.loads(row[0]))
                    else:
                        recipients.update(row[0])
                return list(recipients)
            return []
        except Exception as e:
            self.logger.error(f"Error getting report recipients: {str(e)}")
            return []
