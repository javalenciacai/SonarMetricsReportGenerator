import logging
import logging.handlers
import os
from services.sonarcloud import SonarCloudAPI
from services.metrics_processor import MetricsProcessor
from datetime import datetime
import traceback
import time
from requests.exceptions import RequestException

# Configure logging with file handler to avoid Streamlit context
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add file handler to avoid Streamlit context dependency
file_handler = logging.handlers.RotatingFileHandler(
    'metrics_updater.log',
    maxBytes=1024*1024,
    backupCount=5
)
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(file_handler)

def validate_sonarcloud_token(token):
    """Validate SonarCloud token before making API calls"""
    try:
        api = SonarCloudAPI(token)
        valid, message = api.validate_token()
        if not valid:
            logger.error(f"SonarCloud token validation failed: {message}")
            return False, message
        return True, "Token validated successfully"
    except Exception as e:
        logger.error(f"Error validating SonarCloud token: {str(e)}")
        return False, str(e)

def retry_api_call(func, *args, max_retries=3, retry_delay=5):
    """Retry API calls with exponential backoff"""
    for attempt in range(max_retries):
        try:
            return func(*args)
        except RequestException as e:
            if attempt == max_retries - 1:
                raise
            wait_time = retry_delay * (2 ** attempt)
            logger.warning(f"API call failed, retrying in {wait_time} seconds... Error: {str(e)}")
            time.sleep(wait_time)
    return None

def update_entity_metrics(entity_type, entity_id):
    """Update metrics for an entity (project or group) with enhanced logging and verification"""
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
        'api_responses': []
    }
    
    try:
        sonar_token = os.getenv('SONARCLOUD_TOKEN')
        if not sonar_token:
            error_msg = "SonarCloud token not found in environment variables"
            logger.error(f"[{execution_id}] {error_msg}")
            metrics_summary.update({'status': 'failed', 'errors': [error_msg]})
            return False

        # Validate token before proceeding
        valid, message = validate_sonarcloud_token(sonar_token)
        if not valid:
            metrics_summary.update({'status': 'failed', 'errors': [message]})
            return False

        sonar_api = SonarCloudAPI(sonar_token)
        metrics_processor = MetricsProcessor()
        
        if entity_type == 'repository':
            logger.info(f"[{execution_id}] Fetching metrics for repository: {entity_id}")
            try:
                # Retry API call with exponential backoff
                metrics = retry_api_call(sonar_api.get_project_metrics, entity_id)
                
                if metrics:
                    metrics_dict = {m['metric']: float(m['value']) for m in metrics}
                    logger.debug(f"[{execution_id}] Retrieved metrics: {list(metrics_dict.keys())}")
                    metrics_summary['api_responses'].append({
                        'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        'metrics_count': len(metrics_dict),
                        'metrics_keys': list(metrics_dict.keys())
                    })
                    
                    success = metrics_processor.store_metrics(entity_id, "", metrics_dict)
                    if success:
                        metrics_summary['updated_count'] += 1
                        logger.info(f"[{execution_id}] Successfully updated repository metrics")
                        logger.debug(f"[{execution_id}] Metrics values: {metrics_dict}")
                    else:
                        metrics_summary['failed_count'] += 1
                        error_msg = "Failed to store metrics in database"
                        logger.error(f"[{execution_id}] {error_msg}")
                        metrics_summary['errors'].append(error_msg)
                        return False
                else:
                    error_msg = "No metrics data received from SonarCloud API"
                    logger.warning(f"[{execution_id}] {error_msg}")
                    metrics_summary['errors'].append(error_msg)
                    return False
                    
            except Exception as e:
                error_msg = f"Error fetching repository metrics: {str(e)}"
                logger.error(f"[{execution_id}] {error_msg}")
                logger.debug(f"[{execution_id}] Traceback: {traceback.format_exc()}")
                metrics_summary.update({'status': 'failed', 'errors': [error_msg]})
                return False
                
        elif entity_type == 'group':
            logger.info(f"[{execution_id}] Updating metrics for group: {entity_id}")
            try:
                projects = metrics_processor.get_projects_in_group(entity_id)
                if not projects:
                    error_msg = f"No projects found in group {entity_id}"
                    logger.warning(f"[{execution_id}] {error_msg}")
                    metrics_summary['errors'].append(error_msg)
                    return False
                
                logger.info(f"[{execution_id}] Found {len(projects)} projects in group")
                
                for project in projects:
                    logger.debug(f"[{execution_id}] Processing project: {project['name']} ({project['repo_key']})")
                    try:
                        metrics = retry_api_call(sonar_api.get_project_metrics, project['repo_key'])
                        if metrics:
                            metrics_dict = {m['metric']: float(m['value']) for m in metrics}
                            metrics_summary['api_responses'].append({
                                'project': project['name'],
                                'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                'metrics_count': len(metrics_dict)
                            })
                            
                            if metrics_processor.store_metrics(project['repo_key'], project['name'], metrics_dict):
                                metrics_summary['updated_count'] += 1
                                logger.debug(f"[{execution_id}] Successfully updated metrics for {project['name']}")
                            else:
                                metrics_summary['failed_count'] += 1
                                error_msg = f"Failed to store metrics for {project['name']}"
                                logger.error(f"[{execution_id}] {error_msg}")
                                metrics_summary['errors'].append(error_msg)
                    except Exception as e:
                        metrics_summary['failed_count'] += 1
                        error_msg = f"Error updating {project['name']}: {str(e)}"
                        logger.error(f"[{execution_id}] {error_msg}")
                        metrics_summary['errors'].append(error_msg)
                
                logger.info(f"[{execution_id}] Group update summary: "
                        f"Updated {metrics_summary['updated_count']}/{len(projects)} projects, "
                        f"Failed {metrics_summary['failed_count']} projects")
                
                return metrics_summary['updated_count'] > 0
                
            except Exception as e:
                error_msg = f"Error updating group: {str(e)}"
                logger.error(f"[{execution_id}] {error_msg}")
                logger.debug(f"[{execution_id}] Traceback: {traceback.format_exc()}")
                metrics_summary.update({'status': 'failed', 'errors': [error_msg]})
                return False
        
        metrics_summary['status'] = 'success'
        logger.info(f"[{execution_id}] Metrics update completed successfully")
        return True
        
    except Exception as e:
        error_msg = f"Error in metrics update execution: {str(e)}"
        logger.error(f"[{execution_id}] {error_msg}")
        logger.debug(f"[{execution_id}] Traceback: {traceback.format_exc()}")
        metrics_summary.update({'status': 'failed', 'errors': [error_msg]})
        return False
    
    finally:
        end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        metrics_summary['end_time'] = end_time
        logger.info(f"[{execution_id}] Execution completed at {end_time}")
        logger.info(f"[{execution_id}] Final status: {metrics_summary['status']}")
        if metrics_summary['errors']:
            logger.info(f"[{execution_id}] Errors encountered: {len(metrics_summary['errors'])}")
            for error in metrics_summary['errors']:
                logger.debug(f"[{execution_id}] Error details: {error}")
