from database.connection import execute_query
from datetime import datetime, timezone

class MetricsProcessor:
    @staticmethod
    def store_metrics(repo_key, name, metrics):
        """Store metrics and track project existence"""
        try:
            # Store repository and update last_seen timestamp using UTC
            repo_query = """
            INSERT INTO repositories (repo_key, name, last_seen, is_active)
            VALUES (%s, %s, CURRENT_TIMESTAMP AT TIME ZONE 'UTC', true)
            ON CONFLICT (repo_key) DO UPDATE
            SET name = EXCLUDED.name,
                last_seen = CURRENT_TIMESTAMP AT TIME ZONE 'UTC',
                is_active = true
            RETURNING id;
            """
            result = execute_query(repo_query, (repo_key, name))
            if not result:
                raise Exception("Failed to get repository ID")
            repo_id = result[0][0]

            # Store metrics with all required columns using UTC timestamp
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
            (m.timestamp AT TIME ZONE 'UTC')::text as timestamp
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
            (m.timestamp AT TIME ZONE 'UTC')::text as timestamp,
            r.last_seen AT TIME ZONE 'UTC' as last_seen,
            r.is_active,
            r.is_marked_for_deletion,
            CURRENT_TIMESTAMP AT TIME ZONE 'UTC' - r.last_seen AT TIME ZONE 'UTC' as inactive_duration
        FROM metrics m
        JOIN repositories r ON r.id = m.repository_id
        WHERE r.repo_key = %s
        ORDER BY m.timestamp DESC
        LIMIT 1;
        """
        result = execute_query(query, (repo_key,))
        return dict(result[0]) if result else None

    @staticmethod
    def get_projects_in_group(group_id):
        """Get all projects in a specific group"""
        query = """
        SELECT 
            repo_key,
            name,
            is_active,
            last_seen AT TIME ZONE 'UTC' as last_seen,
            created_at AT TIME ZONE 'UTC' as created_at,
            CURRENT_TIMESTAMP AT TIME ZONE 'UTC' - last_seen AT TIME ZONE 'UTC' as inactive_duration
        FROM repositories
        WHERE group_id = %s
        ORDER BY name;
        """
        result = execute_query(query, (group_id,))
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
            last_seen AT TIME ZONE 'UTC' as last_seen,
            created_at AT TIME ZONE 'UTC' as created_at,
            group_id,
            CURRENT_TIMESTAMP AT TIME ZONE 'UTC' - last_seen AT TIME ZONE 'UTC' as inactive_duration,
            (SELECT row_to_json(m.*)
             FROM metrics m
             WHERE m.repository_id = r.id
             ORDER BY m.timestamp DESC
             LIMIT 1) as latest_metrics
        FROM repositories r
        ORDER BY 
            is_active DESC,
            last_seen DESC;
        """
        result = execute_query(query)
        return [dict(row) for row in result] if result else []
