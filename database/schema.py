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
        last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """
    execute_query(create_repositories_table)

    # Create tags table
    create_tags_table = """
    CREATE TABLE IF NOT EXISTS tags (
        id SERIAL PRIMARY KEY,
        name VARCHAR(50) NOT NULL,
        color VARCHAR(7) NOT NULL DEFAULT '#808080',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """
    execute_query(create_tags_table)

    # Create repository_tags table for many-to-many relationship
    create_repository_tags_table = """
    CREATE TABLE IF NOT EXISTS repository_tags (
        repository_id INTEGER REFERENCES repositories(id) ON DELETE CASCADE,
        tag_id INTEGER REFERENCES tags(id) ON DELETE CASCADE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (repository_id, tag_id)
    );
    """
    execute_query(create_repository_tags_table)

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

    # Add columns to metrics if they don't exist
    alter_metrics = """
    DO $$
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                      WHERE table_name='metrics' AND column_name='ncloc') THEN
            ALTER TABLE metrics ADD COLUMN ncloc INTEGER DEFAULT 0;
        END IF;

        IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                      WHERE table_name='metrics' AND column_name='sqale_index') THEN
            ALTER TABLE metrics ADD COLUMN sqale_index INTEGER DEFAULT 0;
        END IF;
    END $$;
    """
    execute_query(alter_metrics)

# Tag management functions
def create_tag(name, color='#808080'):
    """Create a new tag"""
    query = """
    INSERT INTO tags (name, color)
    VALUES (%s, %s)
    RETURNING id;
    """
    try:
        result = execute_query(query, (name, color))
        return result[0][0] if result else None
    except Exception as e:
        print(f"Error creating tag: {str(e)}")
        return None

def get_all_tags():
    """Get all available tags"""
    query = """
    SELECT id, name, color, created_at
    FROM tags
    ORDER BY name;
    """
    try:
        result = execute_query(query)
        return [dict(zip(['id', 'name', 'color', 'created_at'], row)) for row in result]
    except Exception as e:
        print(f"Error getting tags: {str(e)}")
        return []

def get_project_tags(repo_key):
    """Get all tags for a specific project"""
    query = """
    SELECT t.id, t.name, t.color, t.created_at
    FROM tags t
    JOIN repository_tags rt ON rt.tag_id = t.id
    JOIN repositories r ON r.id = rt.repository_id
    WHERE r.repo_key = %s
    ORDER BY t.name;
    """
    try:
        result = execute_query(query, (repo_key,))
        return [dict(zip(['id', 'name', 'color', 'created_at'], row)) for row in result]
    except Exception as e:
        print(f"Error getting project tags: {str(e)}")
        return []

def add_tag_to_project(repo_key, tag_id):
    """Add a tag to a project"""
    query = """
    INSERT INTO repository_tags (repository_id, tag_id)
    SELECT r.id, %s
    FROM repositories r
    WHERE r.repo_key = %s
    ON CONFLICT DO NOTHING
    RETURNING repository_id;
    """
    try:
        result = execute_query(query, (tag_id, repo_key))
        return bool(result)
    except Exception as e:
        print(f"Error adding tag to project: {str(e)}")
        return False

def remove_tag_from_project(repo_key, tag_id):
    """Remove a tag from a project"""
    query = """
    DELETE FROM repository_tags rt
    USING repositories r
    WHERE rt.repository_id = r.id
    AND r.repo_key = %s
    AND rt.tag_id = %s;
    """
    try:
        execute_query(query, (repo_key, tag_id))
        return True
    except Exception as e:
        print(f"Error removing tag from project: {str(e)}")
        return False

def delete_tag(tag_id):
    """Delete a tag (will also remove it from all projects)"""
    query = """
    DELETE FROM tags
    WHERE id = %s;
    """
    try:
        execute_query(query, (tag_id,))
        return True
    except Exception as e:
        print(f"Error deleting tag: {str(e)}")
        return False

# Existing functions...
def mark_project_for_deletion(repo_key):
    """Mark a project for deletion"""
    query = """
    UPDATE repositories
    SET is_marked_for_deletion = true
    WHERE repo_key = %s;
    """
    try:
        execute_query(query, (repo_key,))
        return True, "Project marked for deletion"
    except Exception as e:
        return False, f"Error marking project for deletion: {str(e)}"

def unmark_project_for_deletion(repo_key):
    """Remove deletion mark from a project"""
    query = """
    UPDATE repositories
    SET is_marked_for_deletion = false
    WHERE repo_key = %s;
    """
    try:
        execute_query(query, (repo_key,))
        return True, "Deletion mark removed"
    except Exception as e:
        return False, f"Error removing deletion mark: {str(e)}"

def delete_project_data(repo_key):
    """Delete all data for a specific project that is marked for deletion"""
    # First check if the project is marked for deletion
    check_query = """
    SELECT is_marked_for_deletion FROM repositories WHERE repo_key = %s;
    """
    try:
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
