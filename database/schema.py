from database.connection import execute_query

def initialize_database():
    """Initialize database with all required tables and columns"""
    # Create repositories table
    create_repositories_table = """
    CREATE TABLE IF NOT EXISTS repositories (
        id SERIAL PRIMARY KEY,
        repo_key VARCHAR(255) UNIQUE NOT NULL,
        name VARCHAR(255) NOT NULL,
        is_active BOOLEAN DEFAULT true,
        is_marked_for_deletion BOOLEAN DEFAULT false,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        group_id INTEGER
    );
    """
    execute_query(create_repositories_table)

    # Create project groups table
    create_groups_table = """
    CREATE TABLE IF NOT EXISTS project_groups (
        id SERIAL PRIMARY KEY,
        name VARCHAR(255) NOT NULL,
        description TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """
    execute_query(create_groups_table)

    # Add columns to repositories if they don't exist
    alter_repositories = """
    DO $$
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                      WHERE table_name='repositories' AND column_name='last_seen') THEN
            ALTER TABLE repositories ADD COLUMN last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
        END IF;

        IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                      WHERE table_name='repositories' AND column_name='is_marked_for_deletion') THEN
            ALTER TABLE repositories ADD COLUMN is_marked_for_deletion BOOLEAN DEFAULT false;
        END IF;

        IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                      WHERE table_name='repositories' AND column_name='is_active') THEN
            ALTER TABLE repositories ADD COLUMN is_active BOOLEAN DEFAULT true;
        END IF;

        IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                      WHERE table_name='repositories' AND column_name='group_id') THEN
            ALTER TABLE repositories ADD COLUMN group_id INTEGER REFERENCES project_groups(id);
        END IF;
    END $$;
    """
    execute_query(alter_repositories)

    # Create metrics table
    create_metrics_table = """
    CREATE TABLE IF NOT EXISTS metrics (
        id SERIAL PRIMARY KEY,
        repository_id INTEGER REFERENCES repositories(id),
        bugs INTEGER DEFAULT 0,
        vulnerabilities INTEGER DEFAULT 0,
        code_smells INTEGER DEFAULT 0,
        coverage FLOAT DEFAULT 0,
        duplicated_lines_density FLOAT DEFAULT 0,
        ncloc INTEGER DEFAULT 0,
        sqale_index INTEGER DEFAULT 0,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """
    execute_query(create_metrics_table)

    # Create policy acceptance table
    create_policy_table = """
    CREATE TABLE IF NOT EXISTS policy_acceptance (
        id SERIAL PRIMARY KEY,
        user_token VARCHAR(255) UNIQUE NOT NULL,
        accepted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """
    execute_query(create_policy_table)

def mark_project_for_deletion(repo_key):
    """Mark a project for deletion"""
    mark_query = """
    UPDATE repositories
    SET is_marked_for_deletion = true
    WHERE repo_key = %s;
    """
    try:
        execute_query(mark_query, (repo_key,))
        return True, "Project marked for deletion"
    except Exception as e:
        return False, f"Error marking project for deletion: {str(e)}"

def unmark_project_for_deletion(repo_key):
    """Remove deletion mark from a project"""
    unmark_query = """
    UPDATE repositories
    SET is_marked_for_deletion = false
    WHERE repo_key = %s;
    """
    try:
        execute_query(unmark_query, (repo_key,))
        return True, "Deletion mark removed"
    except Exception as e:
        return False, f"Error removing deletion mark: {str(e)}"

def delete_project_data(repo_key):
    """Delete all data for a specific project that is marked for deletion"""
    try:
        # First check if the project is marked for deletion
        check_query = """
        SELECT is_marked_for_deletion FROM repositories WHERE repo_key = %s;
        """
        result = execute_query(check_query, (repo_key,))
        if not result or not result[0][0]:
            return False, "Project must be marked for deletion first"

        # Delete metrics first due to foreign key constraint
        delete_metrics_query = """
        DELETE FROM metrics
        WHERE repository_id = (SELECT id FROM repositories WHERE repo_key = %s);
        """
        execute_query(delete_metrics_query, (repo_key,))

        # Then delete the repository
        delete_repo_query = """
        DELETE FROM repositories
        WHERE repo_key = %s;
        """
        execute_query(delete_repo_query, (repo_key,))
        
        return True, "Project data deleted successfully"
    except Exception as e:
        return False, f"Error deleting project data: {str(e)}"

def check_policy_acceptance(user_token):
    """Check if a user has accepted the policies"""
    query = """
    SELECT EXISTS(
        SELECT 1 FROM policy_acceptance 
        WHERE user_token = %s
    );
    """
    try:
        result = execute_query(query, (user_token,))
        return result[0][0] if result else False
    except Exception as e:
        print(f"Error checking policy acceptance: {str(e)}")
        return False

def store_policy_acceptance(user_token):
    """Store user's policy acceptance"""
    query = """
    INSERT INTO policy_acceptance (user_token, accepted_at, last_updated)
    VALUES (%s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
    ON CONFLICT (user_token) 
    DO UPDATE SET last_updated = CURRENT_TIMESTAMP;
    """
    try:
        execute_query(query, (user_token,))
        return True
    except Exception as e:
        print(f"Error storing policy acceptance: {str(e)}")
        return False

def create_project_group(name, description):
    """Create a new project group"""
    query = """
    INSERT INTO project_groups (name, description)
    VALUES (%s, %s)
    RETURNING id;
    """
    try:
        result = execute_query(query, (name, description))
        return result[0][0] if result else None
    except Exception as e:
        print(f"Error creating project group: {str(e)}")
        return None

def get_project_groups():
    """Get all project groups"""
    query = """
    SELECT id, name, description, created_at
    FROM project_groups
    ORDER BY name;
    """
    try:
        result = execute_query(query)
        return [dict(row) for row in result] if result else []
    except Exception as e:
        print(f"Error getting project groups: {str(e)}")
        return []

def assign_project_to_group(repo_key, group_id):
    """Assign a project to a group"""
    query = """
    UPDATE repositories
    SET group_id = %s
    WHERE repo_key = %s;
    """
    try:
        execute_query(query, (group_id, repo_key))
        return True
    except Exception as e:
        print(f"Error assigning project to group: {str(e)}")
        return False

def remove_project_from_group(repo_key):
    """Remove a project from its group"""
    query = """
    UPDATE repositories
    SET group_id = NULL
    WHERE repo_key = %s;
    """
    try:
        execute_query(query, (repo_key,))
        return True
    except Exception as e:
        print(f"Error removing project from group: {str(e)}")
        return False
