from database.connection import execute_query
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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

    # Create tags table with updated_at column
    create_tags_table = """
    CREATE TABLE IF NOT EXISTS tags (
        id SERIAL PRIMARY KEY,
        name VARCHAR(50) UNIQUE NOT NULL,
        color VARCHAR(7) NOT NULL DEFAULT '#808080',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """
    execute_query(create_tags_table)

    # Add updated_at column if it doesn't exist
    add_updated_at = """
    DO $$ 
    BEGIN 
        IF NOT EXISTS (
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'tags' AND column_name = 'updated_at'
        ) THEN
            ALTER TABLE tags ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
        END IF;
    END $$;
    """
    execute_query(add_updated_at)

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
    """Create a new tag with improved transaction handling"""
    try:
        execute_query("BEGIN")
        
        try:
            # Check if tag exists with lock
            check_query = """
            SELECT EXISTS(
                SELECT 1 FROM tags WHERE name = %s
                FOR UPDATE
            )
            """
            result = execute_query(check_query, (name,))
            
            if result[0][0]:  # Tag exists
                execute_query("ROLLBACK")
                return None, "Tag with this name already exists"

            # Create new tag
            insert_query = """
            INSERT INTO tags (name, color, created_at, updated_at)
            VALUES (%s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            RETURNING id
            """
            result = execute_query(insert_query, (name, color))
            execute_query("COMMIT")
            
            if result:
                return result[0][0], "Tag created successfully"
            return None, "Failed to create tag"
            
        except Exception as inner_e:
            execute_query("ROLLBACK")
            raise inner_e
            
    except Exception as e:
        logger.error(f"Error creating tag: {str(e)}")
        return None, f"Error creating tag: {str(e)}"

def get_all_tags():
    """Get all available tags with error handling"""
    query = """
    SELECT id, name, color, created_at, updated_at
    FROM tags
    ORDER BY name
    """
    try:
        result = execute_query(query)
        return [dict(zip(['id', 'name', 'color', 'created_at', 'updated_at'], row)) for row in result]
    except Exception as e:
        logger.error(f"Error getting tags: {str(e)}")
        return []

def edit_tag(tag_id, name=None, color=None):
    """Edit an existing tag with optimistic locking"""
    try:
        execute_query("BEGIN")
        try:
            # Check if tag exists and lock for update
            check_query = """
            SELECT name, color FROM tags 
            WHERE id = %s
            FOR UPDATE
            """
            result = execute_query(check_query, (tag_id,))
            
            if not result:
                execute_query("ROLLBACK")
                return False, "Tag not found"
            
            current_name, current_color = result[0]
            name = name if name is not None else current_name
            color = color if color is not None else current_color
            
            # Check if new name conflicts with existing tags
            if name != current_name:
                name_check_query = """
                SELECT EXISTS(
                    SELECT 1 FROM tags 
                    WHERE name = %s AND id != %s
                    FOR UPDATE
                )
                """
                name_check = execute_query(name_check_query, (name, tag_id))
                if name_check[0][0]:
                    execute_query("ROLLBACK")
                    return False, "Tag name already exists"
            
            # Update tag
            update_query = """
            UPDATE tags 
            SET name = %s,
                color = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
            RETURNING id
            """
            result = execute_query(update_query, (name, color, tag_id))
            
            if result:
                execute_query("COMMIT")
                return True, "Tag updated successfully"
            else:
                execute_query("ROLLBACK")
                return False, "Failed to update tag"
                
        except Exception as inner_e:
            execute_query("ROLLBACK")
            raise inner_e
            
    except Exception as e:
        error_msg = f"Error updating tag: {str(e)}"
        logger.error(error_msg)
        return False, error_msg

def get_project_tags(repo_key):
    """Get all tags for a specific project"""
    query = """
    SELECT t.id, t.name, t.color, t.created_at, t.updated_at
    FROM tags t
    JOIN repository_tags rt ON rt.tag_id = t.id
    JOIN repositories r ON r.id = rt.repository_id
    WHERE r.repo_key = %s
    ORDER BY t.name
    """
    try:
        result = execute_query(query, (repo_key,))
        return [dict(zip(['id', 'name', 'color', 'created_at', 'updated_at'], row)) for row in result]
    except Exception as e:
        logger.error(f"Error getting project tags: {str(e)}")
        return []

def add_tag_to_project(repo_key, tag_id):
    """Add a tag to a project with improved transaction handling and locking"""
    logger.info(f"Attempting to add tag {tag_id} to project {repo_key}")
    
    try:
        # Start transaction
        execute_query("BEGIN")
        
        try:
            # Lock the necessary tables in the correct order to prevent deadlocks
            execute_query("LOCK TABLE repositories, repository_tags IN ACCESS EXCLUSIVE MODE")
            
            # Get repository ID with lock
            repo_query = """
            SELECT id FROM repositories 
            WHERE repo_key = %s 
            FOR UPDATE
            """
            repo_result = execute_query(repo_query, (repo_key,))
            
            if not repo_result:
                execute_query("ROLLBACK")
                logger.warning(f"Project {repo_key} not found")
                return {"success": False, "status": "not_found"}
            
            repo_id = repo_result[0][0]
            
            # Check if tag is already assigned
            check_query = """
            SELECT EXISTS (
                SELECT 1 
                FROM repository_tags rt
                WHERE rt.repository_id = %s AND rt.tag_id = %s
                FOR UPDATE
            )
            """
            result = execute_query(check_query, (repo_id, tag_id))
            
            if result[0][0]:  # Tag already exists
                execute_query("COMMIT")
                logger.info(f"Tag {tag_id} already assigned to project {repo_key}")
                return {"success": True, "status": "already_exists"}
            
            # Insert the tag
            insert_query = """
            INSERT INTO repository_tags (repository_id, tag_id)
            VALUES (%s, %s)
            ON CONFLICT DO NOTHING
            RETURNING repository_id
            """
            result = execute_query(insert_query, (repo_id, tag_id))
            
            # Commit the transaction
            execute_query("COMMIT")
            
            if result:
                logger.info(f"Successfully added tag {tag_id} to project {repo_key}")
                return {"success": True, "status": "added"}
            else:
                logger.warning(f"Tag {tag_id} already exists for project {repo_key}")
                return {"success": True, "status": "already_exists"}
                
        except Exception as inner_e:
            execute_query("ROLLBACK")
            raise inner_e
            
    except Exception as e:
        error_msg = f"Error adding tag to project: {str(e)}"
        logger.error(error_msg)
        return {"success": False, "status": "error", "message": error_msg}

def remove_tag_from_project(repo_key, tag_id):
    """Remove a tag from a project with improved error handling"""
    logger.info(f"Attempting to remove tag {tag_id} from project {repo_key}")
    
    try:
        # Start transaction
        execute_query("BEGIN")
        
        try:
            # Lock the tables in the correct order to prevent deadlocks
            execute_query("LOCK TABLE repositories, repository_tags IN ACCESS EXCLUSIVE MODE")
            
            # Get repository ID with lock
            repo_query = """
            SELECT id FROM repositories 
            WHERE repo_key = %s 
            FOR UPDATE
            """
            repo_result = execute_query(repo_query, (repo_key,))
            
            if not repo_result:
                execute_query("ROLLBACK")
                logger.warning(f"Project {repo_key} not found")
                return False
            
            repo_id = repo_result[0][0]
            
            # Delete the tag association
            delete_query = """
            DELETE FROM repository_tags 
            WHERE repository_id = %s 
            AND tag_id = %s
            RETURNING tag_id
            """
            result = execute_query(delete_query, (repo_id, tag_id))
            
            if result:
                # Commit the transaction
                execute_query("COMMIT")
                logger.info(f"Successfully removed tag {tag_id} from project {repo_key}")
                return True
            else:
                execute_query("ROLLBACK")
                logger.warning(f"Tag {tag_id} not found for project {repo_key}")
                return False
                
        except Exception as inner_e:
            execute_query("ROLLBACK")
            raise inner_e
            
    except Exception as e:
        error_msg = f"Error removing tag from project: {str(e)}"
        logger.error(error_msg)
        return False

def delete_tag(tag_id):
    """Delete a tag (will also remove it from all projects)"""
    try:
        execute_query("BEGIN")
        
        query = """
        DELETE FROM tags
        WHERE id = %s
        RETURNING id
        """
        result = execute_query(query, (tag_id,))
        
        if result:
            execute_query("COMMIT")
            return True
        else:
            execute_query("ROLLBACK")
            return False
    except Exception as e:
        execute_query("ROLLBACK")
        logger.error(f"Error deleting tag: {str(e)}")
        return False

def check_policy_acceptance(user_token):
    """Check if a user has accepted the policies"""
    query = """
    SELECT EXISTS(
        SELECT 1 FROM policy_acceptance 
        WHERE user_token = %s
    )
    """
    try:
        result = execute_query(query, (user_token,))
        return result[0][0] if result else False
    except Exception as e:
        logger.error(f"Error checking policy acceptance: {str(e)}")
        return False

def store_policy_acceptance(user_token):
    """Store user's policy acceptance"""
    try:
        query = """
        INSERT INTO policy_acceptance (user_token, accepted_at, last_updated)
        VALUES (%s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        ON CONFLICT (user_token) 
        DO UPDATE SET last_updated = CURRENT_TIMESTAMP
        """
        execute_query(query, (user_token,))
        return True
    except Exception as e:
        logger.error(f"Error storing policy acceptance: {str(e)}")
        return False
