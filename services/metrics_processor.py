import pandas as pd
from database.connection import execute_query
from datetime import datetime, timedelta

class MetricsProcessor:
    @staticmethod
    def store_metrics(repo_key, name, metrics):
        """Store metrics and track project existence"""
        try:
            # Store repository and update last_seen timestamp
            repo_query = """
            INSERT INTO repositories (repo_key, name, last_seen, is_active)
            VALUES (%s, %s, CURRENT_TIMESTAMP, true)
            ON CONFLICT (repo_key) DO UPDATE
            SET name = EXCLUDED.name,
                last_seen = CURRENT_TIMESTAMP,
                is_active = true
            RETURNING id;
            """
            result = execute_query(repo_query, (repo_key, name))
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
        WHERE r.repo_key = %s AND r.is_active = true
        ORDER BY m.timestamp DESC;
        """
        result = execute_query(query, (repo_key,))
        return [dict(row) for row in result] if result else []

    @staticmethod
    def get_inactive_projects(days=30):
        """Get projects that haven't been updated in the specified number of days"""
        query = """
        SELECT 
            repo_key,
            name,
            last_seen,
            created_at,
            is_marked_for_deletion
        FROM repositories
        WHERE last_seen < CURRENT_TIMESTAMP - INTERVAL '%s days'
            AND is_active = true
        ORDER BY last_seen DESC;
        """
        result = execute_query(query, (days,))
        return [dict(row) for row in result] if result else []

    @staticmethod
    def get_project_status():
        """Get status of all projects including active and inactive ones"""
        query = """
        SELECT 
            repo_key,
            name,
            is_active,
            is_marked_for_deletion,
            last_seen,
            created_at,
            CURRENT_TIMESTAMP - last_seen as inactive_duration
        FROM repositories
        ORDER BY last_seen DESC;
        """
        result = execute_query(query)
        return [dict(row) for row in result] if result else []

    @staticmethod
    def mark_project_inactive(repo_key):
        """Mark a project as inactive"""
        query = """
        UPDATE repositories
        SET is_active = false
        WHERE repo_key = %s;
        """
        try:
            execute_query(query, (repo_key,))
            return True, "Project marked as inactive"
        except Exception as e:
            return False, f"Error marking project as inactive: {str(e)}"
