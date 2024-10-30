import pandas as pd
from database.connection import execute_query
from datetime import datetime, timedelta
from database.schema import mark_project_for_deletion, unmark_project_for_deletion, delete_project_data

class MetricsProcessor:
    @staticmethod
    def store_metrics(repo_key, name, metrics, reset_failures=False):
        """Store metrics and track project existence"""
        try:
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
                raise Exception("Failed to get repository ID")
            repo_id = result[0][0]

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
            return True
        except Exception as e:
            print(f"Error storing metrics: {str(e)}")
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
            result = execute_query(query, (repo_key,))
            if result and result[0]:
                failures, is_active = result[0]
                if not is_active:
                    # If project became inactive, check for auto-deletion criteria
                    MetricsProcessor.check_auto_deletion_criteria(repo_key)
                return failures
            return None
        except Exception as e:
            print(f"Error incrementing consecutive failures: {str(e)}")
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
          AND consecutive_failures >= 5;
        """
        try:
            execute_query(query, (repo_key,))
            return True
        except Exception as e:
            print(f"Error checking auto-deletion criteria: {str(e)}")
            return False

    @staticmethod
    def mark_project_inactive(repo_key):
        """Mark a project as inactive"""
        query = """
        UPDATE repositories
        SET is_active = false,
            last_seen = CURRENT_TIMESTAMP,
            consecutive_failures = CASE 
                WHEN consecutive_failures < 3 THEN 3 
                ELSE consecutive_failures 
            END
        WHERE repo_key = %s
        RETURNING id;
        """
        try:
            result = execute_query(query, (repo_key,))
            if result:
                # Check for auto-deletion criteria after marking inactive
                MetricsProcessor.check_auto_deletion_criteria(repo_key)
                return True
            return False
        except Exception as e:
            print(f"Error marking project inactive: {str(e)}")
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
        result = execute_query(query, (repo_key,))
        return [dict(row) for row in result] if result else []

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
        result = execute_query(query, (repo_key,))
        return dict(result[0]) if result else None

    @staticmethod
    def check_and_mark_inactive_projects(active_project_keys):
        """Check and mark projects as inactive if they are not in the active projects list"""
        if not active_project_keys:
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
            result = execute_query(query, (tuple(active_project_keys),))
            marked_inactive = result[0][0] if result and result[0][0] else []
            
            # Check auto-deletion criteria for newly inactive projects
            for repo_key in marked_inactive:
                MetricsProcessor.check_auto_deletion_criteria(repo_key)
            
            return True, f"Marked {len(marked_inactive)} projects as inactive"
        except Exception as e:
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
        result = execute_query(query)
        return [dict(row) for row in result] if result else []

    @staticmethod
    def mark_project_for_deletion(repo_key):
        """Mark a project for deletion"""
        return mark_project_for_deletion(repo_key)

    @staticmethod
    def unmark_project_for_deletion(repo_key):
        """Remove deletion mark from a project"""
        return unmark_project_for_deletion(repo_key)

    @staticmethod
    def delete_project_data(repo_key):
        """Delete all data for a specific project"""
        return delete_project_data(repo_key)
