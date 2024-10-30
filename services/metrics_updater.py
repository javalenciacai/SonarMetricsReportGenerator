import logging
from services.sonarcloud import SonarCloudAPI
from services.metrics_processor import MetricsProcessor
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def update_entity_metrics(entity_type, entity_id):
    """Update metrics for an entity (project or group)"""
    logger.info(f"Starting metrics update for {entity_type} {entity_id}")
    
    try:
        sonar_token = os.getenv('SONARCLOUD_TOKEN')
        sonar_api = SonarCloudAPI(sonar_token)
        metrics_processor = MetricsProcessor()
        
        if entity_type == 'repository':
            logger.info(f"Fetching metrics for repository: {entity_id}")
            metrics = sonar_api.get_project_metrics(entity_id)
            if metrics:
                metrics_dict = {m['metric']: float(m['value']) for m in metrics}
                success = metrics_processor.store_metrics(entity_id, "", metrics_dict)
                if success:
                    logger.info(f"Successfully updated metrics for repository: {entity_id}")
                else:
                    logger.error(f"Failed to store metrics for repository: {entity_id}")
        elif entity_type == 'group':
            logger.info(f"Updating metrics for group: {entity_id}")
            projects = metrics_processor.get_projects_in_group(entity_id)
            updated_count = 0
            for project in projects:
                logger.debug(f"Fetching metrics for group project: {project['repo_key']}")
                metrics = sonar_api.get_project_metrics(project['repo_key'])
                if metrics:
                    metrics_dict = {m['metric']: float(m['value']) for m in metrics}
                    if metrics_processor.store_metrics(project['repo_key'], project['name'], metrics_dict):
                        updated_count += 1
            logger.info(f"Updated metrics for {updated_count}/{len(projects)} projects in group {entity_id}")
        
        logger.info(f"Completed metrics update for {entity_type} {entity_id}")
        return True
    except Exception as e:
        logger.error(f"Error updating metrics for {entity_type} {entity_id}: {str(e)}")
        return False
