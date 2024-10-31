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
from datetime import datetime, timezone
import requests

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

scheduler = SchedulerService()
report_generator = None
notification_service = None

def register_repository_jobs():
    """Register update jobs for all repositories with their stored intervals"""
    try:
        metrics_processor = MetricsProcessor()
        all_projects = metrics_processor.get_project_status()
        registered_count = 0
        failed_count = 0
        
        logger.info(f"[{datetime.now()}] Starting automatic job registration for {len(all_projects)} repositories")
        
        for project in all_projects:
            if project['is_active']:
                try:
                    prefs = get_update_preferences('repository', project['repo_key'])
                    interval = prefs.get('update_interval', 3600)
                    
                    logger.debug(f"Registering job for repository: {project['repo_key']} "
                                f"with interval: {interval}s")
                    
                    scheduler.schedule_metrics_update(
                        update_entity_metrics,
                        'repository',
                        project['repo_key'],
                        interval
                    )
                    registered_count += 1
                    logger.info(f"Successfully registered job for {project['repo_key']}")
                except Exception as e:
                    failed_count += 1
                    logger.error(f"Failed to register job for {project['repo_key']}: {str(e)}")
        
        logger.info(f"Job registration complete: {registered_count} succeeded, {failed_count} failed")
        return registered_count > 0
    except Exception as e:
        logger.error(f"Error during job registration: {str(e)}")
        return False

def verify_scheduler_status():
    """Verify scheduler status and log active jobs"""
    try:
        if scheduler.scheduler.running:
            active_jobs = scheduler.scheduler.get_jobs()
            logger.info(f"Scheduler is running with {len(active_jobs)} active jobs")
            for job in active_jobs:
                next_run = job.next_run_time.strftime("%Y-%m-%d %H:%M:%S") if job.next_run_time else "Not scheduled"
                logger.info(f"Active job: {job.id}, Next run: {next_run}")
                job_status = scheduler.get_job_status(job.id)
                if job_status:
                    logger.debug(f"Job status: {job_status}")
            return True
        else:
            logger.error("Scheduler is not running")
            return False
    except Exception as e:
        logger.error(f"Error verifying scheduler status: {str(e)}")
        return False

def handle_project_switch():
    """Handle project selection changes without unnecessary refreshes"""
    if 'previous_project' in st.session_state:
        if st.session_state.get('previous_project') != st.session_state.get('selected_project'):
            st.session_state.show_inactive = False
            st.session_state.previous_project = st.session_state.selected_project
            
            # Check project status immediately when switching
            if st.session_state.selected_project and st.session_state.selected_project != 'all':
                try:
                    sonar_api = SonarCloudAPI(st.session_state.sonar_token)
                    metrics_processor = MetricsProcessor()
                    
                    try:
                        # Attempt to fetch project metrics
                        metrics = sonar_api.get_project_metrics(st.session_state.selected_project)
                        if not metrics:
                            # Mark project as inactive if no metrics found
                            metrics_processor.mark_project_inactive(st.session_state.selected_project)
                            logger.warning(f"Project {st.session_state.selected_project} marked as inactive - no metrics found")
                    except requests.exceptions.HTTPError as e:
                        if e.response.status_code == 404:
                            # Immediately mark project as inactive on 404
                            metrics_processor.mark_project_inactive(st.session_state.selected_project)
                            logger.warning(f"Project {st.session_state.selected_project} marked as inactive - not found in SonarCloud")
                        else:
                            raise
                except Exception as e:
                    logger.error(f"Error checking project status: {str(e)}")

def setup_sidebar():
    """Setup sidebar with optimized state management"""
    with st.sidebar:
        st.markdown("""
            <div style="display: flex; justify-content: center; margin-bottom: 1rem;">
                <img src="static/sonarcloud-logo.svg" alt="SonarCloud Logo" style="width: 180px; height: auto;">
            </div>
        """, unsafe_allow_html=True)
        st.markdown("---")
        return st.sidebar

def handle_inactive_project(project_key, metrics_processor):
    """Handle actions for inactive projects"""
    col1, col2 = st.columns([3, 1])
    with col1:
        project_data = metrics_processor.get_latest_metrics(project_key)
        if project_data:
            inactive_duration = project_data.get('inactive_duration')
            last_seen = project_data.get('last_seen')
            st.warning(f"""
                ⚠️ This project appears to be inactive.
                - Last seen: {last_seen}
                - Inactive for: {inactive_duration}
            """)
    
    with col2:
        is_marked = project_data and project_data.get('is_marked_for_deletion', False)
        if is_marked:
            if st.button("🔄 Unmark for Deletion"):
                success, msg = metrics_processor.unmark_project_for_deletion(project_key)
                if success:
                    st.success("✅ Project unmarked for deletion")
                    st.rerun()
                else:
                    st.error(f"Failed to unmark project: {msg}")
            
            if st.button("🗑️ Permanently Delete", type="primary"):
                success, msg = metrics_processor.delete_project_data(project_key)
                if success:
                    st.success("✅ Project deleted successfully")
                    st.rerun()
                else:
                    st.error(f"Failed to delete project: {msg}")
        else:
            if st.button("⚠️ Mark for Deletion"):
                success, msg = metrics_processor.mark_project_for_deletion(project_key)
                if success:
                    st.success("✅ Project marked for deletion")
                    st.rerun()
                else:
                    st.error(f"Failed to mark project: {msg}")

def display_project_card(project_key, project_name, metrics_data, is_inactive=False, is_marked_for_deletion=False):
    """Display a project card with metrics and status"""
    status_prefix = "🗑️" if is_marked_for_deletion else "⚠️" if is_inactive else "✅"
    
    # Get update interval and last update
    update_interval = get_update_preferences('repository', project_key).get('update_interval', 3600)
    interval_display = format_update_interval(update_interval)
    
    last_update = metrics_data.get('timestamp') if metrics_data else None
    last_update_display = format_last_update(last_update)
    
    st.markdown(f"""
        <div class="project-card">
            <h3 style="color: #FAFAFA;">{status_prefix} {project_name}</h3>
            <div class="update-interval">
                <span>⏱️ Update interval: {interval_display}</span>
                <span>•</span>
                <span>🕒 {last_update_display}</span>
            </div>
            <div class="metric-grid">
    """, unsafe_allow_html=True)
    
    if metrics_data:
        metrics_dict = {
            'ncloc': metrics_data.get('ncloc', 0),
            'bugs': metrics_data.get('bugs', 0),
            'vulnerabilities': metrics_data.get('vulnerabilities', 0),
            'code_smells': metrics_data.get('code_smells', 0),
            'coverage': metrics_data.get('coverage', 0),
            'duplicated_lines_density': metrics_data.get('duplicated_lines_density', 0),
            'sqale_index': metrics_data.get('sqale_index', 0)
        }
        display_current_metrics(metrics_dict)
    else:
        st.info("No metrics data available for this project")
    
    st.markdown("</div></div>", unsafe_allow_html=True)

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

        initialize_database()
        
        global report_generator, notification_service

        if not scheduler.scheduler.running:
            logger.info("Starting scheduler service")
            scheduler.start()
            if not verify_scheduler_status():
                st.error("Failed to initialize scheduler service")
                return
                
            logger.info("Registering update jobs for repositories")
            if not register_repository_jobs():
                logger.warning("Failed to register some repository update jobs")
        else:
            logger.info("Scheduler service already running")
            verify_scheduler_status()

        sidebar = setup_sidebar()

        with sidebar:
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

        report_generator = ReportGenerator(sonar_api)
        notification_service = NotificationService(report_generator)
        metrics_processor = MetricsProcessor()
        
        st.success(f"✅ Token validated successfully. Using organization: {sonar_api.organization}")

        if view_mode == "Project Groups":
            manage_project_groups(sonar_api)
            if st.session_state.get('selected_group'):
                st.sidebar.markdown("---")
                with st.sidebar:
                    display_interval_settings(
                        'group',
                        st.session_state.selected_group,
                        scheduler
                    )
        else:
            # Get all projects status
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
                    apply_filter = st.form_submit_button("Apply Filter")
                    
                    if apply_filter:
                        st.session_state.show_inactive_projects = show_inactive

            # Filter projects based on inactive setting
            filtered_projects = {k: v for k, v in project_names.items()}
            if not show_inactive:
                filtered_projects = {k: v for k, v in filtered_projects.items() 
                                  if '⚠️' not in v and '🗑️' not in v or k == 'all'}

            selected_project = st.sidebar.selectbox(
                "Select Project",
                options=list(filtered_projects.keys()),
                format_func=lambda x: filtered_projects.get(x, x),
                key='selected_project',
                on_change=handle_project_switch
            )

            if selected_project == 'all':
                st.markdown("## 📊 All Projects Overview")
                
                # Display active projects
                active_projects = []
                inactive_projects = []
                
                for project_key, status in project_status.items():
                    if status['is_active']:
                        try:
                            metrics = sonar_api.get_project_metrics(project_key)
                            if metrics:
                                metrics_dict = {m['metric']: float(m['value']) for m in metrics}
                                active_projects.append({
                                    'key': project_key,
                                    'name': status['name'],
                                    'metrics': metrics_dict
                                })
                            else:
                                metrics_processor.mark_project_inactive(project_key)
                                logger.warning(f"Project {project_key} marked as inactive - no metrics found")
                        except requests.exceptions.HTTPError as e:
                            if e.response.status_code == 404:
                                metrics_processor.mark_project_inactive(project_key)
                                logger.warning(f"Project {project_key} marked as inactive - not found in SonarCloud")
                    else:
                        # Get historical data for inactive projects
                        latest_metrics = metrics_processor.get_latest_metrics(project_key)
                        if latest_metrics:
                            inactive_projects.append({
                                'key': project_key,
                                'name': status['name'],
                                'metrics': latest_metrics,
                                'is_marked_for_deletion': status['is_marked_for_deletion']
                            })
                
                # Display active projects first
                if active_projects:
                    st.markdown("### ✅ Active Projects")
                    projects_data = {p['key']: {'name': p['name'], 'metrics': p['metrics']} 
                                  for p in active_projects}
                    display_multi_project_metrics(projects_data)
                    plot_multi_project_comparison(projects_data)
                
                # Display inactive projects if enabled
                if show_inactive and inactive_projects:
                    st.markdown("### ⚠️ Inactive Projects")
                    for project in inactive_projects:
                        display_project_card(
                            project['key'],
                            project['name'],
                            project['metrics'],
                            is_inactive=True,
                            is_marked_for_deletion=project['is_marked_for_deletion']
                        )
                
                # Create combined report
                all_projects_data = {}
                for p in active_projects:
                    all_projects_data[p['key']] = {'name': p['name'], 'metrics': p['metrics']}
                if show_inactive:
                    for p in inactive_projects:
                        all_projects_data[p['key']] = {'name': p['name'], 'metrics': p['metrics']}
                
                if all_projects_data:
                    create_download_report(all_projects_data)
            
            elif selected_project:
                project_info = project_status.get(selected_project, {})
                st.markdown(f"## 📊 Project Dashboard: {project_names[selected_project]}")
                
                is_inactive = not project_info.get('is_active', True)
                
                if is_inactive:
                    handle_inactive_project(selected_project, metrics_processor)
                
                try:
                    if is_inactive:
                        # Display historical data for inactive project
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
                        # Display current data for active project
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
                except requests.exceptions.HTTPError as e:
                    if e.response.status_code == 404 and not is_inactive:
                        metrics_processor.mark_project_inactive(selected_project)
                        st.warning("⚠️ Project not found in SonarCloud. Marked as inactive.")
                        st.rerun()
                    elif is_inactive:
                        st.info("Using historical data for inactive project")
                    else:
                        st.error(f"Failed to fetch metrics: {str(e)}")
                except Exception as e:
                    st.error(f"Error displaying project data: {str(e)}")

    except Exception as e:
        st.error(f"An error occurred: {str(e)}")
        logger.error(f"Main application error: {str(e)}", exc_info=True)

if __name__ == "__main__":
    main()
