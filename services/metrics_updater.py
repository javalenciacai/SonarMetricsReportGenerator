def update_entity_metrics(entity_type, entity_id):
    """Update metrics for an entity (project or group)"""
    from services.sonarcloud import SonarCloudAPI
    from services.metrics_processor import MetricsProcessor
    import os
    
    try:
        sonar_token = os.getenv('SONARCLOUD_TOKEN')
        sonar_api = SonarCloudAPI(sonar_token)
        metrics_processor = MetricsProcessor()
        
        if entity_type == 'repository':
            metrics = sonar_api.get_project_metrics(entity_id)
            if metrics:
                metrics_dict = {m['metric']: float(m['value']) for m in metrics}
                metrics_processor.store_metrics(entity_id, "", metrics_dict)
        elif entity_type == 'group':
            projects = metrics_processor.get_projects_in_group(entity_id)
            for project in projects:
                metrics = sonar_api.get_project_metrics(project['repo_key'])
                if metrics:
                    metrics_dict = {m['metric']: float(m['value']) for m in metrics}
                    metrics_processor.store_metrics(project['repo_key'], project['name'], metrics_dict)
    except Exception as e:
        print(f"Error updating metrics for {entity_type} {entity_id}: {str(e)}")
