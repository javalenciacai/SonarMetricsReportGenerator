import pandas as pd
from database.connection import execute_query
from datetime import datetime, timedelta
from database.schema import (
    mark_project_for_deletion,
    unmark_project_for_deletion,
    delete_project_data,
    get_projects_in_group as schema_get_projects_in_group
)
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
            # Store repository and update last_seen timestamp
            repo_query = """
            INSERT INTO repositories (
                repo_key, name, last_seen, is_active, consecutive_failures
            )
            VALUES (%s, %s, CURRENT_TIMESTAMP, true, %s)
            ON CONFLICT (repo_key) DO UPDATE
            SET name = EXCLUDED.name,
                last_seen = CURRENT_TIMESTAMP,
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

            # Store metrics with all required columns
            metrics_query = """
            INSERT INTO metrics (
                repository_id, bugs, vulnerabilities, code_smells,
                coverage, duplicated_lines_density, ncloc, sqale_index,
                timestamp
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP);
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

    @staticmethod
    def increment_consecutive_failures(repo_key):
        """Increment the consecutive failures counter for a repository"""
        query = """
        UPDATE repositories 
        SET consecutive_failures = consecutive_failures + 1,
            is_active = CASE 
                WHEN consecutive_failures >= 2 THEN false 
                ELSE is_active 
            END
        WHERE repo_key = %s
        RETURNING consecutive_failures, is_active;
        """
        try:
            logger.debug(f"Incrementing consecutive failures for repository {repo_key}")
            result = execute_query(query, (repo_key,))
            if result and result[0]:
                failures, is_active = result[0]
                logger.info(f"Repository {repo_key} consecutive failures increased to {failures}")
                logger.info(f"Repository {repo_key} active status: {is_active}")
                if not is_active:
                    # If project became inactive, check for auto-deletion criteria
                    MetricsProcessor.check_auto_deletion_criteria(repo_key)
                return failures
            return None
        except Exception as e:
            logger.error(f"Error incrementing consecutive failures for {repo_key}: {str(e)}")
            return None

    @staticmethod
    def check_auto_deletion_criteria(repo_key):
        """Check if project meets criteria for automatic deletion marking"""
        query = """
        UPDATE repositories
        SET is_marked_for_deletion = true
        WHERE repo_key = %s
          AND is_active = false
          AND NOT is_marked_for_deletion
          AND (CURRENT_TIMESTAMP - last_seen) > INTERVAL '30 days'
          AND consecutive_failures >= 5
        RETURNING id;
        """
        try:
            logger.debug(f"Checking auto-deletion criteria for repository {repo_key}")
            result = execute_query(query, (repo_key,))
            if result:
                logger.info(f"Repository {repo_key} marked for auto-deletion")
            return bool(result)
        except Exception as e:
            logger.error(f"Error checking auto-deletion criteria for {repo_key}: {str(e)}")
            return False

    @staticmethod
    def mark_project_inactive(repo_key):
        """Mark a project as inactive while preserving historical data"""
        logger.info(f"Marking project {repo_key} as inactive")
        query = """
        UPDATE repositories
        SET is_active = false,
            last_seen = CURRENT_TIMESTAMP,
            consecutive_failures = CASE 
                WHEN consecutive_failures < 3 THEN 3 
                ELSE consecutive_failures 
            END
        WHERE repo_key = %s
        RETURNING id, consecutive_failures;
        """
        try:
            result = execute_query(query, (repo_key,))
            if result:
                repo_id, failures = result[0]
                logger.info(f"Project {repo_key} marked as inactive with {failures} consecutive failures")
                logger.debug(f"Project {repo_key} (ID: {repo_id}) status updated in database")
                
                # Verify the update was successful
                verify_query = """
                SELECT is_active, consecutive_failures, last_seen
                FROM repositories
                WHERE repo_key = %s;
                """
                verify_result = execute_query(verify_query, (repo_key,))
                if verify_result:
                    is_active, failures, last_seen = verify_result[0]
                    logger.debug(f"Project {repo_key} status verification - "
                               f"Active: {is_active}, Failures: {failures}, "
                               f"Last seen: {last_seen}")
                
                # Check for auto-deletion criteria after marking inactive
                MetricsProcessor.check_auto_deletion_criteria(repo_key)
                return True
            logger.error(f"Failed to mark project {repo_key} as inactive - no rows updated")
            return False
        except Exception as e:
            logger.error(f"Error marking project {repo_key} as inactive: {str(e)}")
            return False

    @staticmethod
    def get_historical_data(repo_key):
        """Get historical metrics data for a specific project"""
        query = """
        SELECT 
            m.bugs, 
            m.vulnerabilities, 
            m.code_smells, 
            m.coverage, 
            m.duplicated_lines_density,
            m.ncloc,
            m.sqale_index,
            m.timestamp::text as timestamp
        FROM metrics m
        JOIN repositories r ON r.id = m.repository_id
        WHERE r.repo_key = %s
        ORDER BY m.timestamp DESC;
        """
        try:
            logger.debug(f"Retrieving historical data for repository {repo_key}")
            result = execute_query(query, (repo_key,))
            if result:
                logger.debug(f"Retrieved {len(result)} historical records for {repo_key}")
                return [dict(row) for row in result]
            logger.debug(f"No historical data found for repository {repo_key}")
            return []
        except Exception as e:
            logger.error(f"Error retrieving historical data for {repo_key}: {str(e)}")
            return []

    @staticmethod
    def get_latest_metrics(repo_key):
        """Get the most recent metrics for a project"""
        query = """
        SELECT 
            m.bugs, 
            m.vulnerabilities, 
            m.code_smells, 
            m.coverage, 
            m.duplicated_lines_density,
            m.ncloc,
            m.sqale_index,
            m.timestamp::text as timestamp,
            r.last_seen,
            r.is_active,
            r.consecutive_failures,
            r.is_marked_for_deletion,
            CURRENT_TIMESTAMP - r.last_seen as inactive_duration
        FROM metrics m
        JOIN repositories r ON r.id = m.repository_id
        WHERE r.repo_key = %s
        ORDER BY m.timestamp DESC
        LIMIT 1;
        """
        try:
            logger.debug(f"Retrieving latest metrics for repository {repo_key}")
            result = execute_query(query, (repo_key,))
            if result:
                logger.debug(f"Retrieved latest metrics for repository {repo_key}")
                return dict(result[0])
            logger.debug(f"No metrics found for repository {repo_key}")
            return None
        except Exception as e:
            logger.error(f"Error retrieving latest metrics for {repo_key}: {str(e)}")
            return None

    @staticmethod
    def check_and_mark_inactive_projects(active_project_keys):
        """Check and mark projects as inactive if they are not in the active projects list"""
        if not active_project_keys:
            logger.info("No active projects to compare")
            return True, "No active projects to compare"
        
        query = """
        WITH updated AS (
            UPDATE repositories
            SET is_active = false,
                consecutive_failures = CASE 
                    WHEN consecutive_failures < 3 THEN 3 
                    ELSE consecutive_failures 
                END
            WHERE repo_key NOT IN %s
                AND is_active = true
            RETURNING repo_key
        )
        SELECT array_agg(repo_key) as marked_inactive
        FROM updated;
        """
        try:
            logger.debug("Checking and marking inactive projects")
            result = execute_query(query, (tuple(active_project_keys),))
            marked_inactive = result[0][0] if result and result[0][0] else []
            
            # Check auto-deletion criteria for newly inactive projects
            for repo_key in marked_inactive:
                MetricsProcessor.check_auto_deletion_criteria(repo_key)
            
            logger.info(f"Marked {len(marked_inactive)} projects as inactive")
            return True, f"Marked {len(marked_inactive)} projects as inactive"
        except Exception as e:
            logger.error(f"Error updating inactive projects: {str(e)}")
            return False, f"Error updating inactive projects: {str(e)}"

    @staticmethod
    def get_project_status():
        """Get status of all projects including active and inactive ones"""
        query = """
        SELECT 
            repo_key,
            name,
            is_active,
            is_marked_for_deletion,
            consecutive_failures,
            last_seen,
            created_at,
            group_id,
            CURRENT_TIMESTAMP - last_seen as inactive_duration,
            (SELECT row_to_json(m.*)
             FROM metrics m
             WHERE m.repository_id = r.id
             ORDER BY m.timestamp DESC
             LIMIT 1) as latest_metrics
        FROM repositories r
        ORDER BY 
            is_active DESC,
            is_marked_for_deletion,
            last_seen DESC;
        """
        try:
            logger.debug("Retrieving project status for all projects")
            result = execute_query(query)
            if result:
                logger.debug(f"Retrieved status for {len(result)} projects")
                return [dict(row) for row in result]
            logger.debug("No projects found")
            return []
        except Exception as e:
            logger.error(f"Error retrieving project status: {str(e)}")
            return []

    @staticmethod
    def mark_project_for_deletion(repo_key):
        """Mark a project for deletion"""
        logger.info(f"Marking project {repo_key} for deletion")
        return mark_project_for_deletion(repo_key)

    @staticmethod
    def unmark_project_for_deletion(repo_key):
        """Remove deletion mark from a project"""
        logger.info(f"Removing deletion mark from project {repo_key}")
        return unmark_project_for_deletion(repo_key)

    @staticmethod
    def delete_project_data(repo_key):
        """Delete all data for a specific project"""
        logger.info(f"Deleting all data for project {repo_key}")
        return delete_project_data(repo_key)

    @staticmethod
    def get_projects_in_group(group_id):
        """Get all projects in a specific group with their metrics and status"""
        logger.info(f"Getting projects in group {group_id}")
        try:
            # Get projects using the schema function
            projects = schema_get_projects_in_group(group_id)
            
            if not projects:
                logger.debug(f"No projects found in group {group_id}")
                return []
            
            # Enhance project data with additional metrics
            for project in projects:
                latest_metrics = MetricsProcessor.get_latest_metrics(project['repo_key'])
                if latest_metrics:
                    project.update(latest_metrics)
            
            logger.debug(f"Retrieved {len(projects)} projects from group {group_id}")
            return projects
            
        except Exception as e:
            logger.error(f"Error getting projects in group {group_id}: {str(e)}")
            return []

    @staticmethod
    def get_all_projects_metrics():
        """Get metrics for all projects from database"""
        query = '''
        WITH LatestMetrics AS (
            SELECT 
                r.repo_key,
                r.name,
                r.is_active,
                m.bugs,
                m.vulnerabilities,
                m.code_smells,
                m.coverage,
                m.duplicated_lines_density,
                m.ncloc,
                m.sqale_index,
                ROW_NUMBER() OVER (PARTITION BY r.repo_key ORDER BY m.timestamp DESC) as rn
            FROM repositories r
            JOIN metrics m ON m.repository_id = r.id
        )
        SELECT * FROM LatestMetrics WHERE rn = 1;
        '''
        try:
            result = execute_query(query)
            if not result:
                return {}
                
            projects_data = {}
            for row in result:
                metrics_dict = {
                    'bugs': float(row['bugs']),
                    'vulnerabilities': float(row['vulnerabilities']),
                    'code_smells': float(row['code_smells']),
                    'coverage': float(row['coverage']),
                    'duplicated_lines_density': float(row['duplicated_lines_density']),
                    'ncloc': float(row['ncloc']),
                    'sqale_index': float(row['sqale_index'])
                }
                projects_data[row['repo_key']] = {
                    'name': row['name'],
                    'metrics': metrics_dict,
                    'is_active': row['is_active']
                }
            return projects_data
        except Exception as e:
            logger.error(f"Error getting all projects metrics: {str(e)}")
            return {}
