import streamlit as st
import os
from services.sonarcloud import SonarCloudAPI
from services.metrics_processor import MetricsProcessor
from database.schema import initialize_database, get_update_preferences
from database.connection import execute_query
import logging
from datetime import datetime, timezone
import time
import sys
import traceback
from tenacity import retry, stop_after_attempt, wait_exponential

# Configure logging with UTC timezone
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('app.log')
    ]
)
logger = logging.getLogger(__name__)

def initialize_session_state():
    """Initialize session state with proper state management"""
    if "initialized" not in st.session_state:
        st.session_state.initialized = True
        st.session_state.update_in_progress = False
        st.session_state.update_progress = 0.0
        st.session_state.update_message = ""
        st.session_state.update_error = None
        st.session_state.last_update_time = None
        st.session_state.view_mode = "Individual Projects"
        st.session_state.metrics_cache = {}
        st.session_state.update_started = False
        st.session_state.needs_rerun = False
        st.session_state.current_update_task = None
        logger.info("Session state initialized")

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
def fetch_project_metrics(sonar_api, project_key):
    """Fetch metrics for a project with retry mechanism"""
    try:
        metrics = sonar_api.get_project_metrics(project_key)
        if metrics:
            return {m['metric']: float(m['value']) for m in metrics}
        return None
    except Exception as e:
        logger.error(f"Error fetching metrics for {project_key}: {str(e)}")
        raise

def update_metrics_state(progress=None, message=None, error=None, finished=False):
    """Update metrics state in a thread-safe manner"""
    if progress is not None:
        st.session_state.update_progress = progress
    if message is not None:
        st.session_state.update_message = message
    if error is not None:
        st.session_state.update_error = error
        st.session_state.needs_rerun = True
    if finished:
        st.session_state.update_in_progress = False
        st.session_state.last_update_time = datetime.now(timezone.utc)
        st.session_state.current_update_task = None
        if not error:  # Only rerun if no errors occurred
            st.session_state.needs_rerun = True

def process_single_project(sonar_api, metrics_processor, project, total_projects, current_index):
    """Process a single project's metrics update"""
    try:
        progress = current_index / total_projects
        update_metrics_state(
            progress=progress,
            message=f"Updating {project['name']} ({current_index + 1}/{total_projects})"
        )
        
        metrics = fetch_project_metrics(sonar_api, project['key'])
        if metrics:
            metrics_processor.store_metrics(project['key'], project['name'], metrics)
            st.session_state.metrics_cache[project['key']] = metrics
            return True, None
        return False, f"Failed to fetch metrics for {project['name']}"
    except Exception as e:
        logger.error(f"Error processing project {project['key']}: {str(e)}")
        return False, str(e)

def handle_update_metrics(sonar_api, metrics_processor):
    """Handle metrics update with improved UI responsiveness and state management"""
    status_container = st.empty()
    progress_container = st.empty()
    message_container = st.empty()
    
    # Show current status if update is in progress
    if st.session_state.update_in_progress:
        with progress_container:
            st.progress(st.session_state.update_progress)
        with message_container:
            st.info(st.session_state.update_message)
        if st.session_state.update_error:
            with status_container:
                st.error(f"Error: {st.session_state.update_error}")
                if st.button("Retry Update"):
                    st.session_state.update_in_progress = False
                    st.session_state.current_update_task = None
                    st.experimental_rerun()
        return

    # Show update button
    col1, col2 = st.columns([4, 1])
    with col1:
        st.info("🔄 Click the button to update metrics from SonarCloud")
    with col2:
        update_clicked = st.button(
            "Update Metrics",
            disabled=st.session_state.update_in_progress,
            key="update_metrics"
        )
        
        if update_clicked and not st.session_state.update_in_progress:
            st.session_state.update_in_progress = True
            st.session_state.update_error = None
            st.session_state.update_progress = 0.0
            st.session_state.update_message = "Starting update..."
            
            try:
                # Fetch projects
                projects = sonar_api.get_projects()
                if not projects:
                    raise Exception("No projects found")
                
                total_projects = len(projects)
                updated_count = 0
                failed_projects = []
                
                # Process each project
                for i, project in enumerate(projects):
                    success, error = process_single_project(
                        sonar_api, 
                        metrics_processor, 
                        project, 
                        total_projects, 
                        i
                    )
                    
                    if success:
                        updated_count += 1
                    else:
                        failed_projects.append((project['name'], error))
                    
                    # Small delay to prevent UI freeze
                    time.sleep(0.1)
                
                # Update final state
                final_message = f"Updated {updated_count} projects successfully"
                if failed_projects:
                    failed_names = ", ".join(p[0] for p in failed_projects)
                    final_message += f" ({len(failed_projects)} failed: {failed_names})"
                
                update_metrics_state(
                    progress=1.0,
                    message=final_message,
                    finished=True
                )
                
            except Exception as e:
                error_msg = str(e)
                logger.error(f"Error during metrics update: {error_msg}")
                update_metrics_state(
                    error=error_msg,
                    finished=True
                )
                with status_container:
                    st.error(f"❌ Update failed: {error_msg}")

def main():
    """Main application with improved error handling and state management"""
    try:
        st.set_page_config(
            page_title="SonarCloud Metrics Dashboard",
            page_icon="📊",
            layout="wide",
            initial_sidebar_state="expanded"
        )

        # Initialize session state
        initialize_session_state()
        
        # Initialize database
        if not initialize_database():
            st.error("Failed to initialize database. Please check the database connection.")
            return

        # Setup sidebar
        with st.sidebar:
            st.title("SonarCloud Metrics")
            st.markdown("---")
            
            view_mode = st.radio(
                "Select View",
                ["Individual Projects", "Project Groups", "Automated Reports"]
            )
            
            if view_mode != st.session_state.view_mode:
                st.session_state.update_in_progress = False
                st.session_state.view_mode = view_mode
                st.session_state.needs_rerun = True

        # Check for SonarCloud token
        token = os.getenv('SONARCLOUD_TOKEN')
        if not token:
            st.error("SonarCloud token not found. Please configure the environment variable.")
            return

        # Initialize services
        sonar_api = SonarCloudAPI(token)
        metrics_processor = MetricsProcessor()

        # Handle different views
        if view_mode == "Individual Projects":
            handle_update_metrics(sonar_api, metrics_processor)
        elif view_mode == "Project Groups":
            st.title("Project Groups")
            # Project groups functionality will be handled by other components
        else:
            st.title("Automated Reports")
            # Automated reports functionality will be handled by other components

        # Handle rerun if needed
        if st.session_state.needs_rerun:
            st.session_state.needs_rerun = False
            time.sleep(0.1)  # Small delay to prevent UI flicker
            st.experimental_rerun()

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Critical error in main application: {error_msg}\n{traceback.format_exc()}")
        st.error("An unexpected error occurred. Please check the logs and try again.")

if __name__ == "__main__":
    main()
