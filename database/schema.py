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
        name VARCHAR(50) UNIQUE NOT NULL,
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

def create_tag(name, color='#808080'):
    """Create a new tag with duplicate check"""
    # First check if tag exists
    check_query = """
    SELECT EXISTS(
        SELECT 1 FROM tags WHERE name = %s
    );
    """
    try:
        result = execute_query(check_query, (name,))
        if result[0][0]:  # Tag exists
            return None, "Tag with this name already exists"

        # Create new tag if it doesn't exist
        insert_query = """
        INSERT INTO tags (name, color)
        VALUES (%s, %s)
        RETURNING id;
        """
        result = execute_query(insert_query, (name, color))
        if result:
            return result[0][0], "Tag created successfully"  # Return exactly two values
        return None, "Failed to create tag"
    except Exception as e:
        return None, f"Error creating tag: {str(e)}"

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
    """Add a tag to a project with improved duplicate handling"""
    # First check if the tag is already assigned to the project
    check_query = """
    SELECT EXISTS (
        SELECT 1 
        FROM repository_tags rt
        JOIN repositories r ON r.id = rt.repository_id
        WHERE r.repo_key = %s AND rt.tag_id = %s
    );
    """
    try:
        result = execute_query(check_query, (repo_key, tag_id))
        if result[0][0]:  # Tag is already assigned
            return True  # Return success since the desired state is achieved
        
        # If tag is not assigned, add it using a transaction
        insert_query = """
        WITH repo AS (
            SELECT id FROM repositories WHERE repo_key = %s
        )
        INSERT INTO repository_tags (repository_id, tag_id)
        SELECT repo.id, %s
        FROM repo
        WHERE NOT EXISTS (
            SELECT 1 FROM repository_tags rt 
            WHERE rt.repository_id = repo.id AND rt.tag_id = %s
        )
        RETURNING repository_id;
        """
        result = execute_query(insert_query, (repo_key, tag_id, tag_id))
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
