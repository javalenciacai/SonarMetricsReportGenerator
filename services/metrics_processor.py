import pandas as pd
from database.connection import execute_query
from datetime import datetime

class MetricsProcessor:
    @staticmethod
    def store_metrics(repo_key, name, metrics):
        # Store repository
        repo_query = """
        INSERT INTO repositories (repo_key, name)
        VALUES (%s, %s)
        ON CONFLICT (repo_key) DO UPDATE
        SET name = EXCLUDED.name
        RETURNING id;
        """
        result = execute_query(repo_query, (repo_key, name))
        repo_id = result[0][0]

        # Store metrics
        metrics_query = """
        INSERT INTO metrics (repository_id, bugs, vulnerabilities, code_smells, 
                           coverage, duplicated_lines_density)
        VALUES (%s, %s, %s, %s, %s, %s);
        """
        metrics_data = (
            repo_id,
            metrics.get('bugs', 0),
            metrics.get('vulnerabilities', 0),
            metrics.get('code_smells', 0),
            metrics.get('coverage', 0),
            metrics.get('duplicated_lines_density', 0)
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
            m.timestamp::text as timestamp
        FROM metrics m
        JOIN repositories r ON r.id = m.repository_id
        WHERE r.repo_key = %s
        ORDER BY m.timestamp DESC;
        """
        result = execute_query(query, (repo_key,))
        if not result:
            return []
            
        # Convert the result to a list of dictionaries with proper timestamp handling
        return [dict(row) for row in result]
