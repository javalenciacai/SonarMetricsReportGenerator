import logging
import logging.handlers
import os
from services.sonarcloud import SonarCloudAPI
from services.metrics_processor import MetricsProcessor
from datetime import datetime
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
                logger.debug(f"Response data: {json.dumps(response, indent=2)}")
                return response
            else:
                logger.warning(f"API call returned empty response on attempt {attempt + 1}")
                last_response = response
        except RequestException as e:
            last_error = e
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

def update_entity_metrics(entity_type, entity_id):
    """Update metrics for an entity (project or group) with enhanced error handling"""
    execution_id = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{entity_type}_{entity_id}"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
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
        valid, message = sonar_api.validate_token()
        if not valid:
            metrics_summary.update({'status': 'failed', 'errors': [message]})
            return False, metrics_summary
        
        metrics_processor = MetricsProcessor()
        
        if entity_type == 'repository':
            logger.info(f"[{execution_id}] Fetching metrics for repository: {entity_id}")
            try:
                # Get existing project data first
                project_data = metrics_processor.get_latest_metrics(entity_id)
                consecutive_failures = project_data.get('consecutive_failures', 0) if project_data else 0
                
                try:
                    metrics = retry_api_call(sonar_api.get_project_metrics, entity_id)
                    
                    if metrics:
                        # Project exists and returned metrics
                        metrics_dict = {m['metric']: float(m['value']) for m in metrics}
                        logger.debug(f"[{execution_id}] Retrieved metrics: {list(metrics_dict.keys())}")
                        metrics_summary['api_responses'].append({
                            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            'metrics_count': len(metrics_dict),
                            'metrics': metrics_dict
                        })
                        
                        # Reset consecutive failures on successful update
                        success = metrics_processor.store_metrics(entity_id, "", metrics_dict, reset_failures=True)
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
                                'failed_count': 1,
                                'errors': [error_msg]
                            })
                            return False, metrics_summary
                    else:
                        error_msg = "No metrics data received from API"
                        logger.error(f"[{execution_id}] {error_msg}")
                        # Increment consecutive failures
                        new_failures = metrics_processor.increment_consecutive_failures(entity_id)
                        logger.warning(f"[{execution_id}] Consecutive failures increased to {new_failures}")
                        
                        if new_failures and new_failures >= 3:
                            metrics_processor.mark_project_inactive(entity_id)
                            logger.warning(f"[{execution_id}] Project marked as inactive after {new_failures} consecutive failures")
                        
                        metrics_summary.update({
                            'status': 'failed',
                            'errors': [error_msg]
                        })
                        return False, metrics_summary
                        
                except RequestException as e:
                    if hasattr(e, 'response') and e.response.status_code == 404:
                        # Project not found in SonarCloud
                        error_msg = f"Project '{entity_id}' not found in SonarCloud"
                        logger.error(f"[{execution_id}] {error_msg}")
                        
                        # Increment consecutive failures and check for inactive marking
                        new_failures = metrics_processor.increment_consecutive_failures(entity_id)
                        logger.warning(f"[{execution_id}] Consecutive failures increased to {new_failures} after 404 response")
                        
                        # Mark project as inactive after 3 consecutive failures
                        if new_failures and new_failures >= 3:
                            metrics_processor.mark_project_inactive(entity_id)
                            logger.warning(f"[{execution_id}] Project marked as inactive after {new_failures} consecutive 404 responses")
                        
                        metrics_summary.update({
                            'status': 'failed',
                            'errors': [error_msg]
                        })
                        return False, metrics_summary
                    raise
                    
            except Exception as e:
                error_msg = f"Error fetching repository metrics: {str(e)}"
                logger.error(f"[{execution_id}] {error_msg}")
                logger.debug(f"[{execution_id}] Traceback: {traceback.format_exc()}")
                
                # Increment consecutive failures
                new_failures = metrics_processor.increment_consecutive_failures(entity_id)
                logger.warning(f"[{execution_id}] Consecutive failures increased to {new_failures}")
                
                # Mark project as inactive if threshold reached
                if new_failures and new_failures >= 3:
                    metrics_processor.mark_project_inactive(entity_id)
                    logger.warning(f"[{execution_id}] Project marked as inactive after {new_failures} consecutive failures")
                
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
                for project in projects:
                    try:
                        metrics = retry_api_call(sonar_api.get_project_metrics, project['repo_key'])
                        if metrics:
                            metrics_dict = {m['metric']: float(m['value']) for m in metrics}
                            metrics_summary['api_responses'].append({
                                'project': project['name'],
                                'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                'metrics': metrics_dict
                            })
                            
                            if metrics_processor.store_metrics(project['repo_key'], project['name'], metrics_dict, reset_failures=True):
                                metrics_summary['updated_count'] += 1
                                active_project_keys.append(project['repo_key'])
                            else:
                                metrics_summary['failed_count'] += 1
                                error_msg = f"Failed to store metrics for {project['name']}"
                                metrics_summary['errors'].append(error_msg)
                    except RequestException as e:
                        metrics_summary['failed_count'] += 1
                        if hasattr(e, 'response') and e.response.status_code == 404:
                            error_msg = f"Project {project['name']} not found in SonarCloud"
                            logger.error(f"[{execution_id}] {error_msg}")
                            new_failures = metrics_processor.increment_consecutive_failures(project['repo_key'])
                            if new_failures and new_failures >= 3:
                                metrics_processor.mark_project_inactive(project['repo_key'])
                        else:
                            error_msg = f"Error updating {project['name']}: {str(e)}"
                            metrics_summary['errors'].append(error_msg)
                            metrics_processor.increment_consecutive_failures(project['repo_key'])
                
                # Update inactive status for projects not found
                if active_project_keys:
                    success, msg = metrics_processor.check_and_mark_inactive_projects(active_project_keys)
                    if not success:
                        logger.error(f"[{execution_id}] {msg}")
                
                metrics_summary['status'] = 'success' if metrics_summary['updated_count'] > 0 else 'failed'
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
