import pandas as pd
from database.connection import execute_query
from datetime import datetime, timedelta
from functools import lru_cache
import logging
import json

class MetricsProcessor:
    _cache = {}  # Class-level cache for database results
    _cache_ttl = 300  # 5 minutes cache TTL
    _last_db_operation = 0  # Timestamp of last database operation
    _db_operation_interval = 0.1  # 100ms between database operations

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)

    @classmethod
    def _get_cache_key(cls, operation, *args, **kwargs):
        """Generate a unique cache key"""
        return f"{operation}:{json.dumps(args, sort_keys=True)}:{json.dumps(kwargs, sort_keys=True)}"

    @classmethod
    def _get_cached_result(cls, cache_key):
        """Get result from cache if valid"""
        if cache_key in cls._cache:
            timestamp, result = cls._cache[cache_key]
            if datetime.now().timestamp() - timestamp < cls._cache_ttl:
                return result
            del cls._cache[cache_key]
        return None

    @classmethod
    def _set_cached_result(cls, cache_key, result):
        """Store result in cache"""
        cls._cache[cache_key] = (datetime.now().timestamp(), result)
        # Clean old cache entries
        current_time = datetime.now().timestamp()
        cls._cache = {k: v for k, v in cls._cache.items() 
                     if current_time - v[0] < cls._cache_ttl}

    @staticmethod
    def store_metrics(repo_key, name, metrics):
        """Store metrics and track project existence with batch processing"""
        try:
            # Start transaction for atomic operations
            execute_query("BEGIN")
            
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
                
                # Commit transaction
                execute_query("COMMIT")
                
                # Clear relevant cache entries
                cache_keys_to_clear = [k for k in MetricsProcessor._cache.keys() 
                                     if repo_key in k]
                for key in cache_keys_to_clear:
                    MetricsProcessor._cache.pop(key, None)
                
                return True
                
            except Exception as inner_e:
                execute_query("ROLLBACK")
                raise inner_e
                
        except Exception as e:
            MetricsProcessor().logger.error(f"Error storing metrics: {str(e)}")
            return False

    @classmethod
    def get_historical_data(cls, repo_key):
        """Get historical metrics data for a specific project with caching"""
        cache_key = cls._get_cache_key("historical_data", repo_key)
        cached_result = cls._get_cached_result(cache_key)
        if cached_result is not None:
            return cached_result

        query = """
        WITH recent_metrics AS (
            SELECT 
                m.bugs, 
                m.vulnerabilities, 
                m.code_smells, 
                m.coverage, 
                m.duplicated_lines_density,
                m.ncloc,
                m.sqale_index,
                m.timestamp::text as timestamp,
                ROW_NUMBER() OVER (ORDER BY m.timestamp DESC) as rn
            FROM metrics m
            JOIN repositories r ON r.id = m.repository_id
            WHERE r.repo_key = %s
            ORDER BY m.timestamp DESC
        )
        SELECT * FROM recent_metrics
        WHERE rn <= 1000;  -- Limit to last 1000 records for performance
        """
        
        try:
            result = execute_query(query, (repo_key,))
            data = [dict(row) for row in result] if result else []
            cls._set_cached_result(cache_key, data)
            return data
        except Exception as e:
            MetricsProcessor().logger.error(f"Error fetching historical data: {str(e)}")
            return []

    @classmethod
    def get_latest_metrics(cls, repo_key):
        """Get the most recent metrics for a project with caching"""
        cache_key = cls._get_cache_key("latest_metrics", repo_key)
        cached_result = cls._get_cached_result(cache_key)
        if cached_result is not None:
            return cached_result

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
            CURRENT_TIMESTAMP - r.last_seen as inactive_duration
        FROM metrics m
        JOIN repositories r ON r.id = m.repository_id
        WHERE r.repo_key = %s
        ORDER BY m.timestamp DESC
        LIMIT 1;
        """
        
        try:
            result = execute_query(query, (repo_key,))
            data = dict(result[0]) if result else None
            cls._set_cached_result(cache_key, data)
            return data
        except Exception as e:
            MetricsProcessor().logger.error(f"Error fetching latest metrics: {str(e)}")
            return None

    @classmethod
    def get_project_status(cls, clear_cache=False):
        """Get status of all projects including active and inactive ones with caching"""
        cache_key = cls._get_cache_key("project_status")
        if not clear_cache:
            cached_result = cls._get_cached_result(cache_key)
            if cached_result is not None:
                return cached_result

        query = """
        WITH latest_metrics AS (
            SELECT DISTINCT ON (repository_id)
                repository_id,
                bugs,
                vulnerabilities,
                code_smells,
                coverage,
                duplicated_lines_density,
                ncloc,
                sqale_index,
                timestamp
            FROM metrics
            ORDER BY repository_id, timestamp DESC
        )
        SELECT 
            r.repo_key,
            r.name,
            r.is_active,
            r.is_marked_for_deletion,
            r.last_seen,
            r.created_at,
            CURRENT_TIMESTAMP - r.last_seen as inactive_duration,
            row_to_json(lm.*) as latest_metrics
        FROM repositories r
        LEFT JOIN latest_metrics lm ON lm.repository_id = r.id
        ORDER BY 
            r.is_active DESC,
            r.last_seen DESC;
        """
        
        try:
            result = execute_query(query)
            data = [dict(row) for row in result] if result else []
            cls._set_cached_result(cache_key, data)
            return data
        except Exception as e:
            MetricsProcessor().logger.error(f"Error fetching project status: {str(e)}")
            return []

    def check_and_mark_inactive_projects(self, active_project_keys):
        '''Mark projects as inactive if they are not in the active_project_keys list'''
        try:
            query = '''
            UPDATE repositories
            SET is_active = FALSE
            WHERE repo_key NOT IN %s
            AND is_active = TRUE
            RETURNING repo_key, name;
            '''
            result = execute_query(query, (tuple(active_project_keys),))
            if result:
                self.logger.info(f"Marked {len(result)} projects as inactive")
            return True
        except Exception as e:
            self.logger.error(f"Error marking inactive projects: {str(e)}")
            return False

    @classmethod
    def clear_cache(cls):
        """Clear all cached data"""
        cls._cache.clear()
