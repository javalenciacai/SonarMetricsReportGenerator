import logging
import logging.handlers
import os
from services.sonarcloud import SonarCloudAPI
from services.metrics_processor import MetricsProcessor
from datetime import datetime, timezone
import traceback
import time
from requests.exceptions import RequestException
import json

# Configure logging with file handler to avoid Streamlit context
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add file handler for persistent logging
file_handler = logging.handlers.RotatingFileHandler(
    'metrics_updater.log',
    maxBytes=1024*1024,
    backupCount=5
)
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(file_handler)

def retry_api_call(func, *args, max_retries=3, retry_delay=5):
    """Retry API calls with exponential backoff and detailed logging"""
    last_error = None
    last_response = None
    
    for attempt in range(max_retries):
        try:
            response = func(*args)
            if response:
                logger.debug(f"API call successful on attempt {attempt + 1}")
                return response
            else:
                logger.warning(f"API call returned empty response on attempt {attempt + 1}")
                last_response = response
        except RequestException as e:
            last_error = e
            if hasattr(e, 'response') and e.response.status_code == 404:
                # Don't retry on 404 responses
                logger.warning(f"Received 404 response, not retrying")
                raise
            
            if attempt == max_retries - 1:
                logger.error(f"API call failed after {max_retries} attempts: {str(e)}")
                if hasattr(e, 'response'):
                    logger.error(f"Last error response: {e.response.text}")
                raise
            
            wait_time = retry_delay * (2 ** attempt)
            logger.warning(f"API call failed on attempt {attempt + 1}, "
                         f"retrying in {wait_time} seconds... Error: {str(e)}")
            time.sleep(wait_time)
    
    if last_error:
        raise last_error
    return last_response

def update_entity_metrics(entity_type, entity_id, preserve_name=False):
    """Update metrics for an entity (project or group) with enhanced error handling"""
    utc_now = datetime.now(timezone.utc)
    execution_id = f"{utc_now.strftime('%Y%m%d_%H%M%S')}_{entity_type}_{entity_id}"
    timestamp = utc_now.strftime("%Y-%m-%d %H:%M:%S")
    
    logger.info(f"[{execution_id}] Starting metrics update execution")
    logger.debug(f"[{execution_id}] Update details - Type: {entity_type}, ID: {entity_id}")
    
    metrics_summary = {
        'start_time': timestamp,
        'status': 'running',
        'updated_count': 0,
        'failed_count': 0,
        'errors': [],
        'api_responses': [],
        'execution_id': execution_id
    }
    
    try:
        sonar_token = os.getenv('SONARCLOUD_TOKEN')
        if not sonar_token:
            error_msg = "SonarCloud token not found in environment variables"
            logger.error(f"[{execution_id}] {error_msg}")
            metrics_summary.update({'status': 'failed', 'errors': [error_msg]})
            return False, metrics_summary
        
        sonar_api = SonarCloudAPI(sonar_token)
        metrics_processor = MetricsProcessor()
        
        if entity_type == 'repository':
            logger.info(f"[{execution_id}] Fetching metrics for repository: {entity_id}")
            try:
                # Get existing project data first
                project_data = metrics_processor.get_latest_metrics(entity_id)
                existing_name = project_data.get('name', "") if project_data else ""
                
                try:
                    metrics = retry_api_call(sonar_api.get_project_metrics, entity_id)
                    if metrics:
                        metrics_dict = {m['metric']: float(m['value']) for m in metrics}
                        logger.debug(f"[{execution_id}] Retrieved metrics: {list(metrics_dict.keys())}")
                        
                        # Use existing name if preserve_name is True and name exists
                        name_to_use = existing_name if preserve_name and existing_name else ""
                        
                        # Reset consecutive failures on successful update
                        success = metrics_processor.store_metrics(entity_id, name_to_use, metrics_dict, reset_failures=True)
                        if success:
                            metrics_summary['updated_count'] += 1
                            metrics_summary['status'] = 'success'
                            logger.info(f"[{execution_id}] Successfully updated repository metrics")
                            return True, metrics_summary
                        else:
                            error_msg = "Failed to store metrics in database"
                            logger.error(f"[{execution_id}] {error_msg}")
                            metrics_summary.update({
                                'status': 'failed',
                                'errors': [error_msg]
                            })
                            return False, metrics_summary
                    
                except RequestException as e:
                    if hasattr(e, 'response') and e.response.status_code == 404:
                        # Project not found in SonarCloud - mark as inactive immediately
                        error_msg = f"Project '{entity_id}' not found in SonarCloud (404 response)"
                        logger.error(f"[{execution_id}] {error_msg}")
                        
                        # Mark project as inactive immediately
                        success = metrics_processor.mark_project_inactive(entity_id)
                        if success:
                            logger.warning(f"[{execution_id}] Project marked as inactive due to 404 response")
                        else:
                            logger.error(f"[{execution_id}] Failed to mark project as inactive")
                        
                        metrics_summary.update({
                            'status': 'failed',
                            'errors': [error_msg],
                            'project_status': 'inactive',
                            'last_known_data': project_data
                        })
                        return False, metrics_summary
                    
                    # Handle other API errors
                    error_msg = f"API error: {str(e)}"
                    logger.error(f"[{execution_id}] {error_msg}")
                    new_failures = metrics_processor.increment_consecutive_failures(entity_id)
                    
                    if new_failures and new_failures >= 3:
                        metrics_processor.mark_project_inactive(entity_id)
                        logger.warning(f"[{execution_id}] Project marked as inactive after {new_failures} consecutive failures")
                    
                    metrics_summary.update({
                        'status': 'failed',
                        'errors': [error_msg]
                    })
                    return False, metrics_summary
                    
            except Exception as e:
                error_msg = f"Error in repository update: {str(e)}"
                logger.error(f"[{execution_id}] {error_msg}")
                logger.debug(f"[{execution_id}] Traceback: {traceback.format_exc()}")
                
                metrics_summary.update({
                    'status': 'failed',
                    'errors': [error_msg]
                })
                return False, metrics_summary
        
        elif entity_type == 'group':
            logger.info(f"[{execution_id}] Updating metrics for group: {entity_id}")
            try:
                projects = metrics_processor.get_projects_in_group(entity_id)
                if not projects:
                    error_msg = f"No projects found in group {entity_id}"
                    logger.warning(f"[{execution_id}] {error_msg}")
                    metrics_summary.update({
                        'status': 'failed',
                        'errors': [error_msg]
                    })
                    return False, metrics_summary
                
                active_project_keys = []
                inactive_projects = []
                
                for project in projects:
                    try:
                        metrics = retry_api_call(sonar_api.get_project_metrics, project['repo_key'])
                        if metrics:
                            metrics_dict = {m['metric']: float(m['value']) for m in metrics}
                            if metrics_processor.store_metrics(project['repo_key'], project['name'], metrics_dict, reset_failures=True):
                                metrics_summary['updated_count'] += 1
                                active_project_keys.append(project['repo_key'])
                            else:
                                metrics_summary['failed_count'] += 1
                                
                    except RequestException as e:
                        if hasattr(e, 'response') and e.response.status_code == 404:
                            # Mark project as inactive immediately
                            metrics_processor.mark_project_inactive(project['repo_key'])
                            inactive_projects.append(project['repo_key'])
                            logger.warning(f"[{execution_id}] Project {project['repo_key']} marked as inactive due to 404")
                        else:
                            metrics_summary['failed_count'] += 1
                            error_msg = f"Error updating {project['name']}: {str(e)}"
                            metrics_summary['errors'].append(error_msg)
                
                if active_project_keys:
                    metrics_processor.check_and_mark_inactive_projects(active_project_keys)
                
                metrics_summary.update({
                    'status': 'success' if metrics_summary['updated_count'] > 0 else 'failed',
                    'inactive_projects': inactive_projects
                })
                return metrics_summary['updated_count'] > 0, metrics_summary
                
            except Exception as e:
                error_msg = f"Error updating group: {str(e)}"
                logger.error(f"[{execution_id}] {error_msg}")
                metrics_summary.update({
                    'status': 'failed',
                    'errors': [error_msg]
                })
                return False, metrics_summary
    
    except Exception as e:
        error_msg = f"Error in metrics update execution: {str(e)}"
        logger.error(f"[{execution_id}] {error_msg}")
        logger.debug(f"[{execution_id}] Traceback: {traceback.format_exc()}")
        metrics_summary.update({
            'status': 'failed',
            'errors': [error_msg]
        })
        return False, metrics_summary
