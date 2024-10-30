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
        group_id INTEGER REFERENCES project_groups(id),
        update_interval INTEGER DEFAULT 3600
    );
    """

    # Create project groups table first (since repositories references it)
    create_groups_table = """
    CREATE TABLE IF NOT EXISTS project_groups (
        id SERIAL PRIMARY KEY,
        name VARCHAR(255) NOT NULL,
        description TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        update_interval INTEGER DEFAULT 3600
    );
    """
    execute_query(create_groups_table)
    execute_query(create_repositories_table)

    # Create update_preferences table
    create_update_preferences_table = """
    CREATE TABLE IF NOT EXISTS update_preferences (
        id SERIAL PRIMARY KEY,
        entity_type VARCHAR(50) NOT NULL,
        entity_id INTEGER NOT NULL,
        update_interval INTEGER NOT NULL DEFAULT 3600,
        last_update TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(entity_type, entity_id)
    );
    """
    execute_query(create_update_preferences_table)

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

def store_update_preferences(entity_type, entity_id, interval):
    """Store update interval preferences"""
    try:
        # For repositories, convert repo_key to id
        if entity_type == 'repository':
            query = "SELECT id FROM repositories WHERE repo_key = %s;"
            result = execute_query(query, (str(entity_id),))
            if result:
                entity_id = result[0][0]
            else:
                return False

        # For groups, verify group exists
        elif entity_type == 'group':
            query = "SELECT id FROM project_groups WHERE id = %s;"
            result = execute_query(query, (int(entity_id),))
            if not result:
                return False

        # Store preferences
        query = """
        INSERT INTO update_preferences (entity_type, entity_id, update_interval)
        VALUES (%s, %s, %s)
        ON CONFLICT (entity_type, entity_id) 
        DO UPDATE SET update_interval = EXCLUDED.update_interval;
        """
        execute_query(query, (entity_type, entity_id, interval))
        return True
    except Exception as e:
        print(f"Error storing update preferences: {str(e)}")
        return False

def get_update_preferences(entity_type, entity_id):
    """Get update interval preferences"""
    try:
        # For repositories, convert repo_key to id
        if entity_type == 'repository':
            query = "SELECT id FROM repositories WHERE repo_key = %s;"
            result = execute_query(query, (str(entity_id),))
            if result:
                entity_id = result[0][0]
            else:
                return {'update_interval': 3600, 'last_update': None}

        query = """
        SELECT update_interval, last_update
        FROM update_preferences
        WHERE entity_type = %s AND entity_id = %s;
        """
        result = execute_query(query, (entity_type, entity_id))
        return dict(result[0]) if result else {'update_interval': 3600, 'last_update': None}
    except Exception as e:
        print(f"Error getting update preferences: {str(e)}")
        return {'update_interval': 3600, 'last_update': None}

def update_last_update_time(entity_type, entity_id):
    """Update the last update timestamp"""
    try:
        # For repositories, convert repo_key to id
        if entity_type == 'repository':
            query = "SELECT id FROM repositories WHERE repo_key = %s;"
            result = execute_query(query, (str(entity_id),))
            if result:
                entity_id = result[0][0]
            else:
                return False

        query = """
        UPDATE update_preferences 
        SET last_update = CURRENT_TIMESTAMP
        WHERE entity_type = %s AND entity_id = %s;
        """
        execute_query(query, (entity_type, entity_id))
        return True
    except Exception as e:
        print(f"Error updating last update time: {str(e)}")
        return False

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

        # Then delete from update_preferences
        delete_prefs_query = """
        DELETE FROM update_preferences
        WHERE entity_type = 'repository' AND entity_id = (
            SELECT id FROM repositories WHERE repo_key = %s
        );
        """
        execute_query(delete_prefs_query, (repo_key,))

        # Finally delete the repository
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
        group_id = result[0][0] if result else None
        
        if group_id:
            # Initialize update preferences for the new group
            store_update_preferences('group', group_id, 3600)
            return group_id
        return None
    except Exception as e:
        print(f"Error creating project group: {str(e)}")
        return None

def get_project_groups():
    """Get all project groups"""
    query = """
    SELECT g.id, g.name, g.description, g.created_at,
           p.update_interval, p.last_update
    FROM project_groups g
    LEFT JOIN update_preferences p ON p.entity_type = 'group' AND p.entity_id = g.id
    ORDER BY g.name;
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
    WHERE repo_key = %s
    RETURNING id;
    """
    try:
        result = execute_query(query, (group_id, repo_key))
        return bool(result)
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

def delete_project_group(group_id):
    """Delete a project group and remove group assignments from projects"""
    try:
        # First remove group assignments from all projects
        remove_assignments_query = """
        UPDATE repositories
        SET group_id = NULL
        WHERE group_id = %s;
        """
        execute_query(remove_assignments_query, (group_id,))
        
        # Remove update preferences
        delete_prefs_query = """
        DELETE FROM update_preferences
        WHERE entity_type = 'group' AND entity_id = %s;
        """
        execute_query(delete_prefs_query, (group_id,))
        
        # Finally delete the group
        delete_group_query = """
        DELETE FROM project_groups
        WHERE id = %s;
        """
        execute_query(delete_group_query, (group_id,))
        
        return True, "Group deleted successfully"
    except Exception as e:
        return False, f"Error deleting group: {str(e)}"
