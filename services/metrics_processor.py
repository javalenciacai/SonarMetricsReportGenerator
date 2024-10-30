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

    def get_project_status(self):
        """Get status of all projects with UTC timestamps"""
        query = """
        SELECT 
            r.repo_key,
            r.name,
            r.is_active,
            r.is_marked_for_deletion,
            r.last_seen AT TIME ZONE 'UTC' as last_seen,
            CASE 
                WHEN r.is_active = false THEN 
                    EXTRACT(epoch FROM (CURRENT_TIMESTAMP - r.last_seen))/86400 
            END as days_inactive
        FROM repositories r
        ORDER BY r.name;
        """
        try:
            result = execute_query(query)
            projects = []
            for row in result:
                project = dict(row)
                if project['days_inactive']:
                    days = int(project['days_inactive'])
                    project['inactive_duration'] = f"{days} {'day' if days == 1 else 'days'}"
                projects.append(project)
            return projects
        except Exception as e:
            logger.error(f"Error getting project status: {str(e)}")
            return []

    def get_historical_data(self, repo_key):
        """Get historical metrics data with UTC timestamps"""
        query = """
        SELECT m.*
        FROM metrics m
        JOIN repositories r ON r.id = m.repository_id
        WHERE r.repo_key = %s
        ORDER BY m.timestamp DESC;
        """
        try:
            result = execute_query(query, (repo_key,))
            return [dict(row) for row in result] if result else []
        except Exception as e:
            logger.error(f"Error getting historical data: {str(e)}")
            return []

    def get_latest_metrics(self, repo_key):
        """Get latest metrics with UTC timestamp"""
        query = """
        SELECT 
            m.*,
            r.is_active,
            r.is_marked_for_deletion,
            r.last_seen AT TIME ZONE 'UTC' as last_seen,
            CASE 
                WHEN r.is_active = false THEN 
                    EXTRACT(epoch FROM (CURRENT_TIMESTAMP - r.last_seen))/86400 
            END as days_inactive
        FROM metrics m
        JOIN repositories r ON r.id = m.repository_id
        WHERE r.repo_key = %s
        ORDER BY m.timestamp DESC
        LIMIT 1;
        """
        try:
            result = execute_query(query, (repo_key,))
            if result:
                data = dict(result[0])
                if data.get('days_inactive'):
                    days = int(data['days_inactive'])
                    data['inactive_duration'] = f"{days} {'day' if days == 1 else 'days'}"
                return data
            return None
        except Exception as e:
            logger.error(f"Error getting latest metrics: {str(e)}")
            return None

    def increment_consecutive_failures(self, repo_key):
        """Increment consecutive failures counter"""
        query = """
        UPDATE repositories
        SET consecutive_failures = consecutive_failures + 1
        WHERE repo_key = %s
        RETURNING consecutive_failures;
        """
        try:
            result = execute_query(query, (repo_key,))
            return result[0][0] if result else None
        except Exception as e:
            logger.error(f"Error incrementing failures: {str(e)}")
            return None

    def mark_project_inactive(self, repo_key):
        """Mark a project as inactive"""
        query = """
        UPDATE repositories
        SET is_active = false,
            last_seen = CURRENT_TIMESTAMP AT TIME ZONE 'UTC'
        WHERE repo_key = %s;
        """
        try:
            execute_query(query, (repo_key,))
            return True
        except Exception as e:
            logger.error(f"Error marking project inactive: {str(e)}")
            return False

    def get_projects_in_group(self, group_id):
        """Get all projects in a group"""
        query = """
        SELECT repo_key, name
        FROM repositories
        WHERE group_id = %s;
        """
        try:
            result = execute_query(query, (group_id,))
            return [dict(row) for row in result] if result else []
        except Exception as e:
            logger.error(f"Error getting projects in group: {str(e)}")
            return []

    def check_and_mark_inactive_projects(self, active_keys):
        """Mark projects not in the active list as inactive"""
        if not active_keys:
            return
        
        placeholders = ','.join(['%s'] * len(active_keys))
        query = f"""
        UPDATE repositories
        SET is_active = false,
            last_seen = CURRENT_TIMESTAMP AT TIME ZONE 'UTC'
        WHERE repo_key NOT IN ({placeholders})
        AND is_active = true;
        """
        try:
            execute_query(query, tuple(active_keys))
            return True
        except Exception as e:
            logger.error(f"Error marking inactive projects: {str(e)}")
            return False
