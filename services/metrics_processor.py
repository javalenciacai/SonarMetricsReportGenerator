import pandas as pd
from database.connection import execute_query
from datetime import datetime, timedelta

class MetricsProcessor:
    @staticmethod
    def store_metrics(repo_key, name, metrics):
        # Store repository and update last_seen timestamp
        repo_query = """
        INSERT INTO repositories (repo_key, name, last_seen)
        VALUES (%s, %s, CURRENT_TIMESTAMP)
        ON CONFLICT (repo_key) DO UPDATE
        SET name = EXCLUDED.name,
            last_seen = CURRENT_TIMESTAMP
        RETURNING id;
        """
        result = execute_query(repo_query, (repo_key, name))
        repo_id = result[0][0]

        # Store metrics
        metrics_query = """
        INSERT INTO metrics (repository_id, bugs, vulnerabilities, code_smells, 
                           coverage, duplicated_lines_density, ncloc, sqale_index)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
        """
        metrics_data = (
            repo_id,
            metrics.get('bugs', 0),
            metrics.get('vulnerabilities', 0),
            metrics.get('code_smells', 0),
            metrics.get('coverage', 0),
            metrics.get('duplicated_lines_density', 0),
            metrics.get('ncloc', 0),
            metrics.get('sqale_index', 0)
        )
        execute_query(metrics_query, metrics_data)

    @staticmethod
    def get_historical_data(repo_key):
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
        if not result:
            return []
            
        return [dict(row) for row in result]

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
