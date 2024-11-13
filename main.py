import streamlit as st
import os
from services.sonarcloud import SonarCloudAPI
from services.metrics_processor import MetricsProcessor
from services.scheduler import SchedulerService
from services.report_generator import ReportGenerator
from services.notification_service import NotificationService
from services.metrics_updater import update_entity_metrics
from components.metrics_display import (
    display_current_metrics, create_download_report, 
    display_metric_trends, display_multi_project_metrics,
    format_update_interval, format_last_update
)
from components.visualizations import plot_metrics_history, plot_multi_project_comparison
from components.policy_display import show_policies, get_policy_acceptance_status
from components.group_management import manage_project_groups
from components.interval_settings import display_interval_settings
from components.automated_reports import display_automated_reports
from database.schema import initialize_database, get_update_preferences
from database.connection import execute_query
import logging
from datetime import datetime, timezone, timedelta
import requests
import time
import sys
import traceback

# Configure logging
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
    """Initialize or reset session state variables with improved error handling"""
    try:
        session_vars = {
            'initialized': True,
            'policies_accepted': False,
            'selected_project': None,
            'selected_group': None,
            'show_inactive': False,
            'previous_project': None,
            'show_inactive_projects': True,
            'sonar_token': None,
            'view_mode': "Individual Projects",
            'update_in_progress': False,
            'last_update_time': {},
            'metrics_cache': {},
            'current_metrics': {},
            'project_metrics': {},
            'historical_data': {},
            'update_locks': {},
            'last_metrics_update': {},
            'update_status': {},
            'update_progress': 0.0,
            'update_message': '',
            'update_error': None,
            'throttle_updates': {},
            'rerun_requested': False,
            'rerun_safe': True,
            'last_rerun_time': 0,
            'update_queue': [],
            'current_update_batch': None,
            'last_successful_update': None,
            'batch_size': 2,
            'update_timeout': 30,
            'last_error_count': 0,
            'consecutive_errors': 0,
            'startup_complete': False
        }
        
        for var, default in session_vars.items():
            if var not in st.session_state:
                st.session_state[var] = default
                
        logger.info("Session state initialized successfully")
        return True
    except Exception as e:
        logger.error(f"Error initializing session state: {str(e)}")
        return False

def handle_startup():
    """Handle application startup with proper error handling"""
    try:
        if not st.session_state.get('startup_complete'):
            logger.info("Starting application initialization")
            initialize_database()
            scheduler = SchedulerService()
            if not scheduler.scheduler.running:
                scheduler.start()
            st.session_state.startup_complete = True
            logger.info("Application initialization completed successfully")
        return True
    except Exception as e:
        logger.error(f"Error during startup: {str(e)}\n{traceback.format_exc()}")
        return False

def can_update_project(project_key, min_interval=5):
    """Check if project can be updated based on throttling rules"""
    if st.session_state.update_in_progress:
        logger.info("Update already in progress")
        return False
    
    if st.session_state.consecutive_errors >= 3:
        logger.warning("Too many consecutive errors, cooling down")
        return False
        
    current_time = time.time()
    last_update = st.session_state.throttle_updates.get(project_key, 0)
    return (current_time - last_update) >= min_interval

def cleanup_session_state():
    """Cleanup session state after updates"""
    logger.info("Cleaning up session state")
    st.session_state.update_in_progress = False
    st.session_state.rerun_requested = False
    st.session_state.update_error = None
    st.session_state.update_progress = 0.0
    st.session_state.update_message = ''
    st.session_state.metrics_cache = {}
    st.session_state.rerun_safe = True
    st.session_state.update_queue = []
    st.session_state.current_update_batch = None
    st.session_state.consecutive_errors = 0
    st.session_state.last_error_count = 0

def safe_rerun():
    """Safely handle rerun requests to prevent infinite loops"""
    current_time = time.time()
    
    if (not st.session_state.rerun_requested and 
        st.session_state.rerun_safe and 
        (current_time - st.session_state.last_rerun_time) > 2):  # Increased minimum interval
        
        logger.info("Requesting safe rerun")
        st.session_state.rerun_requested = True
        st.session_state.rerun_safe = False
        st.session_state.last_rerun_time = current_time
        
        try:
            time.sleep(0.5)  # Small delay to ensure state is properly updated
            st.rerun()
        except Exception as e:
            logger.error(f"Error during rerun: {str(e)}")
            st.session_state.rerun_safe = True
            st.session_state.consecutive_errors += 1

def batch_update_projects(sonar_api, metrics_processor, batch_size=None):
    """Update projects in smaller batches to prevent UI freeze"""
    batch_size = batch_size or st.session_state.batch_size
    
    if not st.session_state.update_queue:
        try:
            projects = sonar_api.get_projects()
            if not projects:
                return False, "No projects found"
            st.session_state.update_queue = projects
            st.session_state.current_update_batch = []
            logger.info(f"Initialized update queue with {len(projects)} projects")
        except Exception as e:
            logger.error(f"Error fetching projects: {str(e)}")
            st.session_state.consecutive_errors += 1
            return False, str(e)
    
    if not st.session_state.current_update_batch:
        st.session_state.current_update_batch = st.session_state.update_queue[:batch_size]
        st.session_state.update_queue = st.session_state.update_queue[batch_size:]
        logger.info(f"Created new batch of {len(st.session_state.current_update_batch)} projects")
    
    return process_update_batch(sonar_api, metrics_processor)

def process_update_batch(sonar_api, metrics_processor):
    """Process a batch of projects for updating with improved error handling"""
    if not st.session_state.current_update_batch:
        st.session_state.last_successful_update = time.time()
        st.session_state.consecutive_errors = 0
        return True, st.session_state.metrics_cache
    
    start_time = time.time()
    try:
        batch = st.session_state.current_update_batch
        total_batches = max(1, len(st.session_state.update_queue) // st.session_state.batch_size + 1)
        current_batch = total_batches - (len(st.session_state.update_queue) // st.session_state.batch_size)
        
        for idx, project in enumerate(batch):
            # Check for timeout
            if time.time() - start_time > st.session_state.update_timeout:
                logger.warning("Update timeout reached")
                raise TimeoutError("Update operation timed out")
                
            if not can_update_project(project['key']):
                logger.info(f"Skipping project {project['key']} due to throttling")
                continue
                
            progress = (current_batch - 1 + (idx + 1) / len(batch)) / total_batches
            st.session_state.update_progress = min(0.99, progress)
            st.session_state.update_message = f"Batch {current_batch}/{total_batches}: Updating {project['name']}"
            
            try:
                metrics = sonar_api.get_project_metrics(project['key'])
                if metrics:
                    metrics_dict = {m['metric']: float(m['value']) for m in metrics}
                    metrics_processor.store_metrics(project['key'], project['name'], metrics_dict)
                    
                    st.session_state.metrics_cache[project['key']] = {
                        'name': project['name'],
                        'metrics': metrics_dict,
                        'is_active': True,
                        'last_update': datetime.now(timezone.utc).isoformat()
                    }
                    
                    st.session_state.last_metrics_update[project['key']] = time.time()
                    st.session_state.update_status[project['key']] = 'success'
                    st.session_state.throttle_updates[project['key']] = time.time()
                    
                time.sleep(0.3)  # Slightly longer delay to ensure UI responsiveness
                
            except Exception as e:
                logger.error(f"Error updating project {project['key']}: {str(e)}")
                st.session_state.update_status[project['key']] = 'error'
                st.session_state.consecutive_errors += 1
                continue
        
        st.session_state.current_update_batch = None
        
        if not st.session_state.update_queue:
            st.session_state.update_progress = 1.0
            st.session_state.update_message = "✅ Update completed successfully!"
            st.session_state.rerun_safe = True
            st.session_state.last_successful_update = time.time()
            st.session_state.consecutive_errors = 0
            return True, st.session_state.metrics_cache
        
        safe_rerun()
        return False, None
        
    except Exception as e:
        logger.error(f"Error in batch update: {str(e)}")
        st.session_state.update_error = str(e)
        st.session_state.update_progress = 1.0
        st.session_state.update_message = f"❌ Update failed: {str(e)}"
        st.session_state.rerun_safe = True
        st.session_state.consecutive_errors += 1
        cleanup_session_state()
        return False, None

def update_all_projects_from_sonarcloud(sonar_api, metrics_processor):
    """Update all projects from SonarCloud with improved progress tracking and error handling"""
    if st.session_state.update_in_progress:
        logger.info("Update already in progress")
        return False, {}

    try:
        logger.info("Starting update for all projects")
        st.session_state.update_in_progress = True
        st.session_state.update_error = None
        st.session_state.update_progress = 0.0
        st.session_state.update_message = "Starting update process..."
        st.session_state.rerun_safe = False
        st.session_state.metrics_cache = {}
        
        return batch_update_projects(sonar_api, metrics_processor)

    except Exception as e:
        logger.error(f"Error in update_all_projects: {str(e)}")
        st.session_state.update_error = str(e)
        st.session_state.update_progress = 1.0
        st.session_state.update_message = f"❌ Update failed: {str(e)}"
        st.session_state.rerun_safe = True
        cleanup_session_state()
        return False, {}

def handle_update_metrics(sonar_api, metrics_processor):
    """Handle metrics update with improved UI responsiveness and error handling"""
    try:
        if st.session_state.update_in_progress:
            st.warning("⚙️ Update in progress, please wait...")
            st.progress(st.session_state.update_progress)
            st.info(st.session_state.update_message)
            return

        col1, col2 = st.columns([4, 1])
        with col1:
            st.info("🔄 Click the button to update metrics from SonarCloud")
        with col2:
            if st.button("Update Metrics", key="update_btn", disabled=st.session_state.update_in_progress):
                with st.spinner("Starting update..."):
                    success, result = update_all_projects_from_sonarcloud(sonar_api, metrics_processor)
                    if success:
                        st.success("✅ Metrics updated successfully!")
                        time.sleep(0.5)  # Brief pause to ensure UI updates
                        st.session_state.update_in_progress = False
                        st.rerun()
                    else:
                        st.error(f"❌ Update failed: {st.session_state.update_error}")
                        cleanup_session_state()

        # Show progress if update is in progress
        if st.session_state.update_in_progress:
            st.progress(st.session_state.update_progress)
            st.info(st.session_state.update_message)
            
            if st.session_state.update_error:
                st.error(f"❌ Error: {st.session_state.update_error}")
                if st.button("Retry Update"):
                    cleanup_session_state()
                    st.rerun()

    except Exception as e:
        logger.error(f"Error in handle_update_metrics: {str(e)}")
        st.error(f"An unexpected error occurred: {str(e)}")
        cleanup_session_state()

def main():
    """Main application with improved error handling and state management"""
    try:
        st.set_page_config(
            page_title="SonarCloud Metrics Dashboard",
            page_icon="📊",
            layout="wide",
            initial_sidebar_state="expanded"
        )

        if not initialize_session_state():
            st.error("Failed to initialize application state. Please refresh the page.")
            return

        if not handle_startup():
            st.error("Failed to start application services. Please check the logs and try again.")
            return

        with st.sidebar:
            st.image("static/sonarcloud-logo.svg", width=180)
            st.markdown("---")
            
            st.markdown("### 📊 Navigation")
            view_mode = st.radio(
                "Select View",
                ["Individual Projects", "Project Groups", "Automated Reports"],
                key="view_mode"
            )

            if view_mode != st.session_state.get('previous_view'):
                cleanup_session_state()
                st.session_state['previous_view'] = view_mode

        token = os.getenv('SONARCLOUD_TOKEN')
        if not token:
            token = st.text_input(
                "Enter SonarCloud Token",
                type="password",
                key="token_input"
            )
        
        if not token:
            st.warning("⚠️ Please enter your SonarCloud token to continue")
            return

        st.session_state.sonar_token = token

        with st.sidebar:
            show_policies()
        
        if not get_policy_acceptance_status(token):
            st.warning("⚠️ Please read and accept the Data Usage Policies and Terms of Service to continue")
            return

        sonar_api = SonarCloudAPI(token)
        is_valid, message = sonar_api.validate_token()
        
        if not is_valid:
            st.error(message)
            return

        metrics_processor = MetricsProcessor()
        st.success(f"✅ Token validated successfully. Using organization: {sonar_api.organization}")

        if view_mode == "Automated Reports":
            display_automated_reports()
        elif view_mode == "Project Groups":
            manage_project_groups(sonar_api)
        else:
            all_projects_status = metrics_processor.get_project_status()
            project_names = {}
            project_status = {}

            for project in all_projects_status:
                status_prefix = "✅"
                if not project['is_active']:
                    status_prefix = "🗑️" if project.get('is_marked_for_deletion') else "⚠️"
                project_names[project['repo_key']] = f"{status_prefix} {project['name']}"
                project_status[project['repo_key']] = {
                    'name': project['name'],
                    'is_active': project['is_active'],
                    'is_marked_for_deletion': project.get('is_marked_for_deletion', False),
                    'latest_metrics': project.get('latest_metrics', {})
                }

            project_names['all'] = "📊 All Projects"

            with st.sidebar:
                st.markdown("### 🔍 Project Selection")
                show_inactive = st.checkbox(
                    "Show Inactive Projects",
                    value=st.session_state.show_inactive_projects
                )
                
                if show_inactive != st.session_state.show_inactive_projects:
                    cleanup_session_state()
                    st.session_state.show_inactive_projects = show_inactive
                    safe_rerun()

            filtered_projects = {k: v for k, v in project_names.items()}
            if not show_inactive:
                filtered_projects = {k: v for k, v in filtered_projects.items() 
                                if k == 'all' or ('⚠️' not in v and '🗑️' not in v)}

            selected_project = st.sidebar.selectbox(
                "Select Project",
                options=list(filtered_projects.keys()),
                format_func=lambda x: filtered_projects.get(x, x),
                key='selected_project'
            )

            if selected_project and selected_project != st.session_state.get('previous_project'):
                cleanup_session_state()
                st.session_state.previous_project = selected_project

            if selected_project == 'all':
                st.markdown("## 📊 All Projects Overview")
                handle_update_metrics(sonar_api, metrics_processor)
                
                if st.session_state.metrics_cache:
                    display_multi_project_metrics(st.session_state.metrics_cache)
                    plot_multi_project_comparison(st.session_state.metrics_cache)
                    create_download_report(st.session_state.metrics_cache)
            else:
                if selected_project in project_status:
                    project_info = project_status[selected_project]
                    st.markdown(f"## {project_info['name']}")
                    
                    handle_update_metrics(sonar_api, metrics_processor)
                    
                    if not project_info['is_active']:
                        st.warning("⚠️ This project is currently inactive")
                    
                    if project_info['is_marked_for_deletion']:
                        st.error("🗑️ This project is marked for deletion")
                    
                    display_interval_settings(selected_project)
                    
                    if st.session_state.metrics_cache and selected_project in st.session_state.metrics_cache:
                        display_current_metrics(st.session_state.metrics_cache[selected_project]['metrics'])
                        historical_data = metrics_processor.get_historical_metrics(selected_project)
                        if historical_data:
                            plot_metrics_history(historical_data)
                            display_metric_trends(historical_data)
                        create_download_report(st.session_state.metrics_cache)

    except Exception as e:
        logger.error(f"Critical error in main application: {str(e)}\n{traceback.format_exc()}")
        st.error(f"""
        An unexpected error occurred. Please try refreshing the page.
        If the problem persists, check the application logs.
        Error: {str(e)}
        """)
        cleanup_session_state()

if __name__ == "__main__":
    main()