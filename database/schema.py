from database.connection import execute_query

def initialize_database():
    create_tables_query = """
    CREATE TABLE IF NOT EXISTS repositories (
        id SERIAL PRIMARY KEY,
        repo_key VARCHAR(255) UNIQUE NOT NULL,
        name VARCHAR(255) NOT NULL,
        is_active BOOLEAN DEFAULT true,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    ALTER TABLE repositories 
    ADD COLUMN IF NOT EXISTS last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP;

    CREATE TABLE IF NOT EXISTS metrics (
        id SERIAL PRIMARY KEY,
        repository_id INTEGER REFERENCES repositories(id),
        bugs INTEGER,
        vulnerabilities INTEGER,
        code_smells INTEGER,
        coverage FLOAT,
        duplicated_lines_density FLOAT,
        ncloc INTEGER,
        sqale_index INTEGER,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """
    execute_query(create_tables_query)

def delete_project_data(repo_key):
    """Delete all data for a specific project"""
    delete_metrics_query = """
    DELETE FROM metrics
    WHERE repository_id = (SELECT id FROM repositories WHERE repo_key = %s);
    """
    delete_repo_query = """
    DELETE FROM repositories
    WHERE repo_key = %s;
    """
    
    try:
        execute_query(delete_metrics_query, (repo_key,))
        execute_query(delete_repo_query, (repo_key,))
        return True, "Project data deleted successfully"
    except Exception as e:
        return False, f"Error deleting project data: {str(e)}"
