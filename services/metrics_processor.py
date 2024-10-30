import pandas as pd
from database.connection import execute_query
from datetime import datetime, timezone, timedelta
from database.schema import mark_project_for_deletion, unmark_project_for_deletion, delete_project_data
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MetricsProcessor:
    @staticmethod
    def store_metrics(repo_key, name, metrics, reset_failures=False):
        """Store metrics and track project existence"""
        try:
            logger.debug(f"Storing metrics for repository {repo_key}")
            # Store repository and update last_seen timestamp in UTC
            repo_query = """
            INSERT INTO repositories (
                repo_key, name, last_seen, is_active, consecutive_failures
            )
            VALUES (%s, %s, CURRENT_TIMESTAMP AT TIME ZONE 'UTC', true, %s)
            ON CONFLICT (repo_key) DO UPDATE
            SET name = EXCLUDED.name,
                last_seen = CURRENT_TIMESTAMP AT TIME ZONE 'UTC',
                is_active = true,
                consecutive_failures = CASE 
                    WHEN %s THEN 0 
                    ELSE repositories.consecutive_failures 
                END
            RETURNING id;
            """
            result = execute_query(repo_query, (repo_key, name, 0, reset_failures))
            if not result:
                logger.error(f"Failed to get repository ID for {repo_key}")
                raise Exception("Failed to get repository ID")
            repo_id = result[0][0]
            logger.debug(f"Repository {repo_key} stored/updated with ID {repo_id}")

            # Store metrics with UTC timestamp
            metrics_query = """
            INSERT INTO metrics (
                repository_id, bugs, vulnerabilities, code_smells,
                coverage, duplicated_lines_density, ncloc, sqale_index,
                timestamp
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP AT TIME ZONE 'UTC');
            """
            metrics_data = (
                repo_id,
                float(metrics.get('bugs', 0)),
                float(metrics.get('vulnerabilities', 0)),
                float(metrics.get('code_smells', 0)),
                float(metrics.get('coverage', 0)),
                float(metrics.get('duplicated_lines_density', 0)),
                float(metrics.get('ncloc', 0)),
                float(metrics.get('sqale_index', 0))
            )
            execute_query(metrics_query, metrics_data)
            logger.debug(f"Metrics stored successfully for repository {repo_key}")
            return True
        except Exception as e:
            logger.error(f"Error storing metrics for {repo_key}: {str(e)}")
            return False

# Rest of the file remains the same
