import logging
from services.sonarcloud import SonarCloudAPI
from services.metrics_processor import MetricsProcessor
import os
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def update_entity_metrics(entity_type, entity_id):
    """Update metrics for an entity (project or group) with enhanced logging"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logger.info(f"[{timestamp}] Starting metrics update for {entity_type} {entity_id}")
    
    try:
        sonar_token = os.getenv('SONARCLOUD_TOKEN')
        if not sonar_token:
            logger.error(f"[{timestamp}] SonarCloud token not found in environment variables")
            return False

        sonar_api = SonarCloudAPI(sonar_token)
        metrics_processor = MetricsProcessor()
        
        if entity_type == 'repository':
            logger.info(f"[{timestamp}] Fetching metrics for repository: {entity_id}")
            try:
                metrics = sonar_api.get_project_metrics(entity_id)
                if metrics:
                    metrics_dict = {m['metric']: float(m['value']) for m in metrics}
                    logger.debug(f"[{timestamp}] Retrieved metrics for {entity_id}: {list(metrics_dict.keys())}")
                    
                    success = metrics_processor.store_metrics(entity_id, "", metrics_dict)
                    if success:
                        logger.info(f"[{timestamp}] Successfully updated metrics for repository: {entity_id}")
                        logger.debug(f"[{timestamp}] Stored metrics values: Bugs={metrics_dict.get('bugs', 0)}, "
                                 f"Vulnerabilities={metrics_dict.get('vulnerabilities', 0)}, "
                                 f"Code Smells={metrics_dict.get('code_smells', 0)}")
                    else:
                        logger.error(f"[{timestamp}] Failed to store metrics for repository: {entity_id}")
                        return False
                else:
                    logger.warning(f"[{timestamp}] No metrics data received for repository: {entity_id}")
                    return False
                    
            except Exception as e:
                logger.error(f"[{timestamp}] Error fetching metrics for repository {entity_id}: {str(e)}")
                return False
                
        elif entity_type == 'group':
            logger.info(f"[{timestamp}] Updating metrics for group: {entity_id}")
            try:
                projects = metrics_processor.get_projects_in_group(entity_id)
                if not projects:
                    logger.warning(f"[{timestamp}] No projects found in group {entity_id}")
                    return False
                
                updated_count = 0
                failed_count = 0
                for project in projects:
                    logger.debug(f"[{timestamp}] Fetching metrics for group project: {project['repo_key']}")
                    try:
                        metrics = sonar_api.get_project_metrics(project['repo_key'])
                        if metrics:
                            metrics_dict = {m['metric']: float(m['value']) for m in metrics}
                            if metrics_processor.store_metrics(project['repo_key'], project['name'], metrics_dict):
                                updated_count += 1
                                logger.debug(f"[{timestamp}] Successfully updated metrics for {project['name']}")
                            else:
                                failed_count += 1
                                logger.error(f"[{timestamp}] Failed to store metrics for {project['name']}")
                    except Exception as e:
                        failed_count += 1
                        logger.error(f"[{timestamp}] Error updating metrics for {project['name']}: {str(e)}")
                
                logger.info(f"[{timestamp}] Group {entity_id} update complete: "
                        f"Updated {updated_count}/{len(projects)} projects, "
                        f"Failed {failed_count} projects")
                
                return updated_count > 0
                
            except Exception as e:
                logger.error(f"[{timestamp}] Error updating group {entity_id}: {str(e)}")
                return False
        
        logger.info(f"[{timestamp}] Completed metrics update for {entity_type} {entity_id}")
        return True
        
    except Exception as e:
        logger.error(f"[{timestamp}] Error updating metrics for {entity_type} {entity_id}: {str(e)}")
        return False
