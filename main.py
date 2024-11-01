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
from database.schema import initialize_database, get_update_preferences
import logging
from datetime import datetime, timezone, timedelta
import requests

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def get_default_date_range():
    """Get default date range (last 30 days)"""
    end_date = datetime.now(timezone.utc).date()
    start_date = end_date - timedelta(days=30)
    return start_date, end_date

def filter_metrics_by_date(metrics_data, start_date, end_date):
    """Filter metrics data based on date range"""
    filtered_data = {}
    for project_key, project_data in metrics_data.items():
        if 'timestamp' in project_data:
            metric_date = datetime.fromisoformat(project_data['timestamp'].replace('Z', '+00:00')).date()
            if start_date <= metric_date <= end_date:
                filtered_data[project_key] = project_data
    return filtered_data

def update_all_projects_data(sonar_api, metrics_processor, start_date=None, end_date=None):
    """Update metrics for all projects from SonarCloud with date filtering"""
    logger.info("Starting update for all projects")
    
    # Get all SonarCloud projects first
    sonar_projects = sonar_api.get_projects()
    project_keys = {p['key']: p['name'] for p in sonar_projects}
    
    # Get existing projects from database
    existing_projects = metrics_processor.get_project_status()
    for project in existing_projects:
        if project['repo_key'] not in project_keys and project['is_active']:
            metrics_processor.mark_project_inactive(project['repo_key'])
            logger.info(f"Marked inactive project that's not in SonarCloud: {project['repo_key']}")
    
    updated_projects = {}
    
    # Update metrics for each project
    for project_key, project_name in project_keys.items():
        try:
            metrics = sonar_api.get_project_metrics(project_key)
            if metrics:
                metrics_dict = {m['metric']: float(m['value']) for m in metrics}
                if metrics_processor.store_metrics(project_key, project_name, metrics_dict, reset_failures=True):
                    updated_projects[project_key] = {
                        'name': project_name,
                        'metrics': metrics_dict,
                        'is_active': True,
                        'timestamp': datetime.now(timezone.utc).isoformat()
                    }
                    logger.info(f"Updated metrics for project: {project_key}")
            else:
                logger.warning(f"No metrics found for project: {project_key}")
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                metrics_processor.mark_project_inactive(project_key)
                logger.warning(f"Project {project_key} marked as inactive - not found in SonarCloud")
            else:
                logger.error(f"Error updating project {project_key}: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error updating project {project_key}: {str(e)}")
    
    # Add inactive projects with their last known metrics
    for project in existing_projects:
        if project['repo_key'] not in updated_projects and not project.get('is_marked_for_deletion'):
            latest_metrics = metrics_processor.get_latest_metrics(project['repo_key'])
            if latest_metrics:
                metrics_dict = {
                    'bugs': float(latest_metrics.get('bugs', 0)),
                    'vulnerabilities': float(latest_metrics.get('vulnerabilities', 0)),
                    'code_smells': float(latest_metrics.get('code_smells', 0)),
                    'coverage': float(latest_metrics.get('coverage', 0)),
                    'duplicated_lines_density': float(latest_metrics.get('duplicated_lines_density', 0)),
                    'ncloc': float(latest_metrics.get('ncloc', 0)),
                    'sqale_index': float(latest_metrics.get('sqale_index', 0))
                }
                updated_projects[project['repo_key']] = {
                    'name': project['name'],
                    'metrics': metrics_dict,
                    'is_active': False,
                    'is_marked_for_deletion': project.get('is_marked_for_deletion', False),
                    'timestamp': latest_metrics.get('timestamp')
                }
    
    # Apply date filtering if dates are provided
    if start_date and end_date:
        updated_projects = filter_metrics_by_date(updated_projects, start_date, end_date)
    
    return updated_projects

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
            default_start, default_end = get_default_date_range()
            st.session_state.start_date = default_start
            st.session_state.end_date = default_end

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
                    ["Individual Projects", "Project Groups"],
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

        if view_mode == "Project Groups":
            manage_project_groups(sonar_api)
        else:
            all_projects_status = metrics_processor.get_project_status()
            project_names = {}
            project_status = {}

            # Build project status dictionary
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

            # Add active projects from SonarCloud
            sonar_projects = sonar_api.get_projects()
            for project in sonar_projects:
                if project['key'] not in project_names:
                    project_names[project['key']] = f"✅ {project['name']}"
                    project_status[project['key']] = {
                        'name': project['name'],
                        'is_active': True,
                        'is_marked_for_deletion': False,
                        'latest_metrics': {}
                    }

            project_names['all'] = "📊 All Projects"

            with st.sidebar:
                st.markdown("### 🔍 Project Selection")
                with st.form(key="project_filter_form"):
                    show_inactive = st.checkbox(
                        "Show Inactive Projects",
                        value=st.session_state.show_inactive_projects
                    )
                    
                    # Add date range selection
                    st.markdown("### 📅 Date Range")
                    start_date = st.date_input(
                        "Start Date",
                        value=st.session_state.start_date,
                        key="start_date"
                    )
                    end_date = st.date_input(
                        "End Date",
                        value=st.session_state.end_date,
                        key="end_date"
                    )
                    
                    apply_filter = st.form_submit_button("Apply Filter")
                    
                    if apply_filter:
                        st.session_state.show_inactive_projects = show_inactive
                        st.session_state.start_date = start_date
                        st.session_state.end_date = end_date

            # Filter projects based on inactive setting
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
                projects_data = update_all_projects_data(
                    sonar_api, 
                    metrics_processor,
                    st.session_state.start_date,
                    st.session_state.end_date
                )
                
                if projects_data:
                    display_multi_project_metrics(projects_data)
                    plot_multi_project_comparison(projects_data)
                    create_download_report(projects_data)
                else:
                    st.info("No projects data available for the selected date range")
            
            elif selected_project:
                project_info = project_status.get(selected_project, {})
                st.markdown(f"## 📊 Project Dashboard: {project_names[selected_project]}")
                
                is_inactive = not project_info.get('is_active', True)
                
                if is_inactive:
                    project_data = metrics_processor.get_latest_metrics(selected_project)
                    if project_data:
                        metrics_dict = {k: float(v) for k, v in project_data.items() 
                                    if k not in ['timestamp', 'last_seen', 'is_active', 'inactive_duration']}
                        display_current_metrics(metrics_dict)
                        
                        historical_data = metrics_processor.get_historical_data(selected_project)
                        if historical_data:
                            plot_metrics_history(historical_data)
                            display_metric_trends(historical_data)
                            create_download_report({selected_project: {
                                'name': project_info['name'],
                                'metrics': metrics_dict
                            }})
                else:
                    try:
                        metrics = sonar_api.get_project_metrics(selected_project)
                        if metrics:
                            metrics_dict = {m['metric']: float(m['value']) for m in metrics}
                            display_current_metrics(metrics_dict)
                            create_download_report({selected_project: {
                                'name': project_info['name'],
                                'metrics': metrics_dict
                            }})
                        else:
                            st.warning("No metrics available for this project")
                    except Exception as e:
                        st.error(f"Error displaying project data: {str(e)}")

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
