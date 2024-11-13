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
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def initialize_session_state():
    """Initialize or reset session state variables"""
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
        'pending_rerun': False,
        'update_status': {},
        'update_progress': {},
        'last_error': None
    }
    
    for var, default in session_vars.items():
        if var not in st.session_state:
            st.session_state[var] = default

def safe_rerun():
    """Safely handle rerun requests to prevent infinite loops"""
    if not st.session_state.get('pending_rerun', False):
        st.session_state.pending_rerun = True
        st.rerun()

def manual_update_metrics(entity_type, entity_id, progress_container):
    """Perform manual update with proper progress tracking and error handling"""
    status_key = f"{entity_type}_{entity_id}"
    
    try:
        # Create dedicated progress containers
        status_container = progress_container.container()
        progress_bar = status_container.progress(0)
        status_text = status_container.empty()
        
        # Check for existing update
        if st.session_state.get('update_locks', {}).get(status_key):
            status_text.warning("⚠️ Update already in progress")
            return False, 0
        
        # Initialize session state variables
        for key in ['update_locks', 'metrics_cache', 'current_metrics', 'project_metrics', 'historical_data', 'last_metrics_update']:
            if key not in st.session_state:
                st.session_state[key] = {}
        
        # Set update lock
        st.session_state.update_locks[status_key] = True
        
        try:
            # Check update frequency
            current_time = datetime.now(timezone.utc).timestamp()
            last_update = st.session_state.last_metrics_update.get(entity_id, 0)
            if (current_time - last_update) < 5:
                status_text.warning("⚠️ Please wait a few seconds between updates")
                return False, 0
            
            # Step 1: Initialize update
            progress_bar.progress(0.2)
            status_text.text("Initializing update...")
            
            # Step 2: Connect to SonarCloud
            progress_bar.progress(0.4)
            status_text.text("Connecting to SonarCloud...")
            
            # Step 3: Perform update
            success, summary = update_entity_metrics(entity_type, entity_id)
            
            if success:
                # Step 4: Process results
                progress_bar.progress(0.6)
                status_text.text("Processing results...")
                
                # Clear cache and update timestamps
                st.session_state.last_metrics_update[entity_id] = current_time
                for cache_key in ['metrics_cache', 'current_metrics', 'project_metrics', 'historical_data']:
                    st.session_state[cache_key].pop(entity_id, None)
                
                # Step 5: Finalize update
                progress_bar.progress(0.8)
                status_text.text("Finalizing update...")
                
                # Step 6: Complete update
                progress_bar.progress(1.0)
                status_text.success("✅ Update completed successfully!")
                
                # Clear any previous errors
                st.session_state.last_error = None
                
                # Schedule a rerun without using experimental_rerun
                if not st.session_state.get('pending_rerun'):
                    st.session_state.pending_rerun = True
                    st.rerun()
                
                return True, summary.get('updated_count', 0)
            else:
                error_msg = summary.get('errors', ['Unknown error'])[0]
                progress_bar.progress(1.0)
                status_text.error(f"Update failed: {error_msg}")
                st.session_state.last_error = error_msg
                return False, 0
                
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Error during update for {entity_id}: {error_msg}")
            progress_bar.progress(1.0)
            status_text.error(f"Error during update: {error_msg}")
            st.session_state.last_error = error_msg
            return False, 0
            
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error in manual_update_metrics for {entity_id}: {error_msg}")
        progress_container.error(f"❌ Error during update: {error_msg}")
        st.session_state.last_error = error_msg
        return False, 0
        
    finally:
        # Always ensure lock is released
        if 'update_locks' in st.session_state:
            st.session_state.update_locks[status_key] = False

def update_all_projects_from_sonarcloud(sonar_api, metrics_processor, progress_bar):
    """Update all projects from SonarCloud with progress tracking"""
    try:
        if st.session_state.get('update_in_progress'):
            logger.info("Update already in progress")
            return False, {}

        st.session_state.update_in_progress = True
        progress_bar.progress(0.1, "Fetching projects from SonarCloud...")
        
        try:
            projects = sonar_api.get_projects()
        except Exception as e:
            logger.error(f"Error fetching projects: {str(e)}")
            progress_bar.progress(1.0, "❌ Failed to fetch projects")
            st.session_state.update_in_progress = False
            return False, {}
        
        if not projects:
            progress_bar.progress(1.0, "❌ No projects found in SonarCloud")
            st.session_state.update_in_progress = False
            return False, {}
            
        total_projects = len(projects)
        updated_projects = {}
        
        for idx, project in enumerate(projects, 1):
            progress = 0.1 + (0.9 * (idx / total_projects))
            progress_bar.progress(progress, f"Updating {project['name']} ({idx}/{total_projects})")
            
            try:
                metrics = sonar_api.get_project_metrics(project['key'])
                if metrics:
                    metrics_dict = {m['metric']: float(m['value']) for m in metrics}
                    metrics_processor.store_metrics(project['key'], project['name'], metrics_dict, reset_failures=True)
                    updated_projects[project['key']] = {
                        'name': project['name'],
                        'metrics': metrics_dict,
                        'is_active': True
                    }
                    st.session_state.last_metrics_update[project['key']] = datetime.now(timezone.utc).timestamp()
            except Exception as e:
                logger.error(f"Error updating project {project['key']}: {str(e)}")
                continue
                
        progress_bar.progress(1.0, "✅ Update completed!")
        st.session_state.update_in_progress = False
        return True, updated_projects
        
    except Exception as e:
        logger.error(f"Error in update_all_projects: {str(e)}")
        progress_bar.progress(1.0, f"❌ Update failed: {str(e)}")
        st.session_state.update_in_progress = False
        return False, {}

def main():
    try:
        st.set_page_config(
            page_title="SonarCloud Metrics Dashboard",
            page_icon="📊",
            layout="wide",
            initial_sidebar_state="expanded"
        )

        # Initialize session state
        initialize_session_state()
        
        # Clear pending rerun flag at the start of the session
        if st.session_state.get('pending_rerun'):
            st.session_state.pending_rerun = False

        # Initialize database
        initialize_database()
        
        # Initialize scheduler
        scheduler = SchedulerService()
        if not scheduler.scheduler.running:
            logger.info("Starting scheduler service")
            scheduler.start()

        # Sidebar setup
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
                st.session_state.update_in_progress = False
                st.session_state.metrics_cache = {}
                st.session_state.current_metrics = {}
                st.session_state.project_metrics = {}
                st.session_state['previous_view'] = view_mode

        # Token validation
        token = os.getenv('SONARCLOUD_TOKEN') or st.text_input(
            "Enter SonarCloud Token",
            type="password",
            key="token_input"
        )
        
        if not token:
            st.warning("⚠️ Please enter your SonarCloud token to continue")
            return

        st.session_state.sonar_token = token

        # Policy acceptance check
        with st.sidebar:
            show_policies()
        
        if not get_policy_acceptance_status(token):
            st.warning("⚠️ Please read and accept the Data Usage Policies and Terms of Service to continue")
            return

        # Initialize API and validate token
        sonar_api = SonarCloudAPI(token)
        is_valid, message = sonar_api.validate_token()
        
        if not is_valid:
            st.error(message)
            return

        # Initialize metrics processor
        metrics_processor = MetricsProcessor()
        
        st.success(f"✅ Token validated successfully. Using organization: {sonar_api.organization}")

        # Display selected view
        if view_mode == "Automated Reports":
            display_automated_reports()
        elif view_mode == "Project Groups":
            manage_project_groups(sonar_api)
        else:
            # Get project status
            all_projects_status = metrics_processor.get_project_status()
            project_names = {}
            project_status = {}

            # Process project status
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

            # Project selection
            with st.sidebar:
                st.markdown("### 🔍 Project Selection")
                show_inactive = st.checkbox(
                    "Show Inactive Projects",
                    value=st.session_state.show_inactive_projects
                )
                
                if show_inactive != st.session_state.show_inactive_projects:
                    st.session_state.show_inactive_projects = show_inactive
                    st.session_state.metrics_cache = {}
                    st.session_state.project_metrics = {}
                    safe_rerun()

            # Filter projects based on status
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

            # Handle project selection change
            if selected_project and selected_project != st.session_state.get('previous_project'):
                st.session_state.metrics_cache.pop(selected_project, None)
                st.session_state.current_metrics.pop(selected_project, None)
                st.session_state.project_metrics.pop(selected_project, None)
                st.session_state.historical_data.pop(selected_project, None)
                st.session_state.previous_project = selected_project

            # Display project view
            if selected_project == 'all':
                st.markdown("## 📊 All Projects Overview")
                
                # Update all projects button
                col1, col2, col3 = st.columns([1, 2, 1])
                with col2:
                    if st.button("🔄 Update All Projects", 
                              use_container_width=True, 
                              disabled=st.session_state.update_in_progress):
                        progress_bar = st.progress(0, "Starting update...")
                        success, projects_data = update_all_projects_from_sonarcloud(
                            sonar_api, 
                            metrics_processor, 
                            progress_bar
                        )
                        if success:
                            st.session_state.metrics_cache = projects_data
                            st.success(f"Updated {len(projects_data)} projects from SonarCloud")
                            safe_rerun()
                        else:
                            st.error("Failed to update projects from SonarCloud")

                st.markdown("---")

                # Display all projects metrics
                st.markdown("### 📊 Project Metrics")
                if 'all' not in st.session_state.project_metrics:
                    st.session_state.project_metrics['all'] = metrics_processor.get_all_projects_metrics()
                
                projects_data = st.session_state.metrics_cache or st.session_state.project_metrics['all']
                if projects_data:
                    display_multi_project_metrics(projects_data)
                    plot_multi_project_comparison(projects_data)
                    create_download_report(projects_data)
                else:
                    st.info("No projects data available")
            
            elif selected_project:
                # Display single project view
                project_info = project_status.get(selected_project, {})
                st.markdown(f"## 📊 Project Dashboard: {project_names[selected_project]}")
                
                is_inactive = not project_info.get('is_active', True)
                
                if not is_inactive:
                    # Initialize progress container outside columns
                    progress_container = st.container()
                    
                    with progress_container:
                        status_key = f"repository_{selected_project}"
                        update_status = st.session_state.update_status.get(status_key)
                        
                        # Create columns for layout
                        col1, col2 = st.columns([3, 1])
                        
                        with col1:
                            st.markdown("### 🔄 Update Controls")
                        
                        with col2:
                            update_enabled = update_status != 'in_progress'
                            if st.button("🔄 Update Metrics", 
                                       use_container_width=True,
                                       disabled=not update_enabled):
                                
                                success, updated_count = manual_update_metrics(
                                    'repository',
                                    selected_project,
                                    progress_container
                                )
                                
                                if success:
                                    st.success(f"✅ Updated {updated_count} metrics")
                                    if not st.session_state.get('pending_rerun'):
                                        st.session_state.pending_rerun = True
                                        st.rerun()
                                        
                    # Display metrics tabs
                    metrics_tabs = st.tabs(["📊 Current Metrics", "📈 Metric Trends"])
                    
                    with metrics_tabs[0]:
                        try:
                            if selected_project not in st.session_state.current_metrics:
                                current_metrics = metrics_processor.get_latest_metrics(selected_project)
                                if current_metrics:
                                    st.session_state.current_metrics[selected_project] = current_metrics
                            
                            current_metrics = st.session_state.current_metrics.get(selected_project)
                            if current_metrics:
                                display_current_metrics(current_metrics)
                                create_download_report({
                                    selected_project: {
                                        'name': project_info['name'],
                                        'metrics': current_metrics
                                    }
                                })
                            else:
                                st.info("No metrics data available")
                        except Exception as e:
                            logger.error(f"Error displaying current metrics: {str(e)}")
                            st.error("Error displaying metrics. Please try updating the metrics.")
                    
                    with metrics_tabs[1]:
                        try:
                            if selected_project not in st.session_state.historical_data:
                                historical_data = metrics_processor.get_historical_data(selected_project)
                                if historical_data:
                                    st.session_state.historical_data[selected_project] = historical_data
                            
                            historical_data = st.session_state.historical_data.get(selected_project)
                            if historical_data:
                                display_metric_trends(historical_data)
                                plot_metrics_history(historical_data)
                            else:
                                st.info("No historical data available")
                        except Exception as e:
                            logger.error(f"Error displaying historical metrics: {str(e)}")
                            st.error("Error displaying historical metrics. Please try updating the metrics.")
                else:
                    st.warning("⚠️ This project is currently inactive.")
                    
                    display_interval_settings(
                        'repository',
                        selected_project,
                        scheduler,
                        metrics_processor
                    )
                
    except Exception as e:
        logger.error(f"Application error: {str(e)}")
        st.error(f"An error occurred: {str(e)}")

if __name__ == "__main__":
    main()