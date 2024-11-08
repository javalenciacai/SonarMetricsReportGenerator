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

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def update_all_projects_data(sonar_api, metrics_processor, progress_bar=None):
    """Update metrics for all projects directly from SonarCloud API"""
    logger.info("Starting fresh update for all projects from SonarCloud")
    
    try:
        # Get fresh project list from SonarCloud
        if progress_bar:
            progress_bar.progress(0.1, "Fetching projects from SonarCloud...")
        
        projects = sonar_api.get_projects()
        if not projects:
            logger.warning("No projects found in SonarCloud")
            if progress_bar:
                progress_bar.progress(1.0, "No projects found in SonarCloud")
            return {}
        
        updated_projects = {}
        total_projects = len(projects)
        
        for idx, project in enumerate(projects, 1):
            if progress_bar:
                progress = 0.1 + (0.9 * (idx / total_projects))
                progress_bar.progress(progress, f"Updating project {idx}/{total_projects}...")
            
            project_key = project['key']
            project_name = project['name']
            
            try:
                # Fetch fresh metrics from SonarCloud
                metrics = sonar_api.get_project_metrics(project_key)
                if metrics:
                    metrics_dict = {m['metric']: float(m['value']) for m in metrics}
                    
                    # Store metrics in database
                    if metrics_processor.store_metrics(project_key, project_name, metrics_dict, reset_failures=True):
                        updated_projects[project_key] = {
                            'name': project_name,
                            'metrics': metrics_dict,
                            'is_active': True,
                            'is_marked_for_deletion': False
                        }
                        logger.info(f"Updated metrics for project: {project_key} ({idx}/{total_projects})")
                    else:
                        logger.error(f"Failed to store metrics for project: {project_key}")
                else:
                    logger.warning(f"No metrics found for project: {project_key}")
                    
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 404:
                    logger.warning(f"Project not found in SonarCloud: {project_key}")
                    metrics_processor.mark_project_inactive(project_key)
                else:
                    logger.error(f"HTTP error fetching metrics for {project_key}: {str(e)}")
            except Exception as e:
                logger.error(f"Error processing project {project_key}: {str(e)}")
        
        if progress_bar:
            progress_bar.progress(1.0, "✅ All projects updated successfully!")
        
        return updated_projects
        
    except Exception as e:
        logger.error(f"Error updating project data: {str(e)}")
        if progress_bar:
            progress_bar.progress(1.0, f"❌ Error: {str(e)}")
        return {}

def manual_update_metrics(entity_type, entity_id, progress_bar):
    """Perform manual update with progress tracking"""
    try:
        progress_bar.progress(0.2, "Initializing update...")
        
        success, summary = update_entity_metrics(entity_type, entity_id)
        
        progress_bar.progress(0.6, "Processing update...")
        
        if success:
            progress_bar.progress(1.0, "✅ Update completed successfully!")
            return True, summary.get('updated_count', 0)
        else:
            error_msg = summary.get('errors', ['Unknown error'])[0]
            progress_bar.progress(1.0, f"❌ Update failed: {error_msg}")
            return False, 0
            
    except Exception as e:
        progress_bar.progress(1.0, f"❌ Error during update: {str(e)}")
        return False, 0

def main():
    try:
        st.set_page_config(
            page_title="SonarCloud Metrics Dashboard",
            page_icon="📊",
            layout="wide",
            initial_sidebar_state="expanded"
        )

        if 'initialized' not in st.session_state:
            st.session_state.initialized = True
            st.session_state.policies_accepted = False
            st.session_state.selected_project = None
            st.session_state.selected_group = None
            st.session_state.show_inactive = False
            st.session_state.previous_project = None
            st.session_state.show_inactive_projects = True
            st.session_state.sonar_token = None
            st.session_state.view_mode = "Individual Projects"
            st.session_state.update_in_progress = False

        initialize_database()
        
        scheduler = SchedulerService()
        if not scheduler.scheduler.running:
            logger.info("Starting scheduler service")
            scheduler.start()

        with st.sidebar:
            st.markdown("""
                <div style="display: flex; justify-content: center; margin-bottom: 1rem;">
                    <img src="static/sonarcloud-logo.svg" alt="SonarCloud Logo" style="width: 180px; height: auto;">
                </div>
            """, unsafe_allow_html=True)
            st.markdown("---")
            
            st.markdown("### 📊 Navigation")
            with st.form(key="navigation_form"):
                view_mode = st.radio(
                    "Select View",
                    ["Individual Projects", "Project Groups", "Automated Reports"],
                    key="view_mode"
                )
                navigation_changed = st.form_submit_button("Update View")

        token = os.getenv('SONARCLOUD_TOKEN') or st.text_input(
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
                with st.form(key="project_filter_form"):
                    show_inactive = st.checkbox(
                        "Show Inactive Projects",
                        value=st.session_state.show_inactive_projects
                    )
                    apply_filter = st.form_submit_button("Apply Filter")
                    
                    if apply_filter:
                        st.session_state.show_inactive_projects = show_inactive

            filtered_projects = {k: v for k, v in project_names.items()}
            if not show_inactive:
                filtered_projects = {k: v for k, v in filtered_projects.items() 
                                if '⚠️' not in v and '🗑️' not in v or k == 'all'}

            selected_project = st.sidebar.selectbox(
                "Select Project",
                options=list(filtered_projects.keys()),
                format_func=lambda x: filtered_projects.get(x, x),
                key='selected_project'
            )

            if selected_project == 'all':
                st.markdown("## 📊 All Projects Overview")
                
                # Add manual update button for all projects
                col1, col2 = st.columns([3, 1])
                with col2:
                    if st.button("🔄 Update All Projects", use_container_width=True):
                        progress_bar = st.progress(0, "Starting update...")
                        projects_data = update_all_projects_data(sonar_api, metrics_processor, progress_bar)
                        if projects_data:
                            st.success(f"Updated {len(projects_data)} projects")
                            st.rerun()
                        else:
                            st.warning("No projects data available")
                
                projects_data = update_all_projects_data(sonar_api, metrics_processor)
                if projects_data:
                    display_multi_project_metrics(projects_data)
                    plot_multi_project_comparison(projects_data)
                    create_download_report(projects_data)
                else:
                    st.info("No projects data available")
            
            elif selected_project:
                project_info = project_status.get(selected_project, {})
                st.markdown(f"## 📊 Project Dashboard: {project_names[selected_project]}")
                
                is_inactive = not project_info.get('is_active', True)
                
                # Add manual update button for individual project
                if not is_inactive:
                    col1, col2 = st.columns([3, 1])
                    with col2:
                        if st.button("🔄 Update Metrics", use_container_width=True):
                            progress_bar = st.progress(0, "Starting update...")
                            success, updated_count = manual_update_metrics(
                                'repository', 
                                selected_project,
                                progress_bar
                            )
                            if success:
                                st.rerun()
                
                current_tab, trends_tab = st.tabs(["📊 Current Metrics", "📈 Metric Trends"])
                
                with current_tab:
                    if is_inactive:
                        project_data = metrics_processor.get_latest_metrics(selected_project)
                        if project_data:
                            metrics_dict = {k: float(v) for k, v in project_data.items() 
                                        if k not in ['timestamp', 'last_seen', 'is_active', 'inactive_duration']}
                            display_current_metrics(metrics_dict)
                    else:
                        try:
                            metrics = metrics_processor.get_latest_metrics(selected_project)
                            if metrics:
                                metrics_dict = {k: float(v) for k, v in metrics.items() 
                                            if k not in ['timestamp', 'last_seen', 'is_active', 'inactive_duration']}
                                display_current_metrics(metrics_dict)
                                create_download_report({selected_project: {
                                    'name': project_info['name'],
                                    'metrics': metrics_dict
                                }})
                            else:
                                st.warning("No metrics available for this project")
                        except Exception as e:
                            st.error(f"Error displaying project data: {str(e)}")

                with trends_tab:
                    historical_data = metrics_processor.get_historical_data(selected_project)
                    if historical_data:
                        display_metric_trends(historical_data)
                    else:
                        st.info("No historical data available for trend analysis")

                if selected_project != 'all' and not is_inactive:
                    st.sidebar.markdown("---")
                    with st.sidebar:
                        display_interval_settings(
                            'repository',
                            selected_project,
                            scheduler
                        )

    except Exception as e:
        st.error(f"An error occurred: {str(e)}")
        logger.error(f"Main application error: {str(e)}", exc_info=True)

if __name__ == "__main__":
    main()
