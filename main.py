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
        'last_metrics_update': {},  # Track last update time per project
        'pending_rerun': False  # New flag to control reruns
    }
    
    for var, default in session_vars.items():
        if var not in st.session_state:
            st.session_state[var] = default

def safe_rerun():
    """Safely handle rerun requests to prevent infinite loops"""
    if not st.session_state.get('pending_rerun', False):
        st.session_state.pending_rerun = True
        st.rerun()

def update_all_projects_from_sonarcloud(sonar_api, metrics_processor, progress_bar):
    """Update all projects from SonarCloud with progress tracking"""
    try:
        if st.session_state.get('update_in_progress'):
            logger.info("Update already in progress")
            return False, {}

        st.session_state.update_in_progress = True
        progress_bar.progress(0.1, "Fetching projects from SonarCloud...")
        projects = sonar_api.get_projects()
        
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
                if not st.session_state.get(f'update_lock_{project["key"]}'):
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
                
        progress_bar.progress(1.0, "✅ Update completed!")
        st.session_state.update_in_progress = False
        return True, updated_projects
        
    except Exception as e:
        logger.error(f"Error in update_all_projects: {str(e)}")
        progress_bar.progress(1.0, f"❌ Update failed: {str(e)}")
        st.session_state.update_in_progress = False
        return False, {}

def manual_update_metrics(entity_type, entity_id, progress_bar):
    """Perform manual update with progress tracking"""
    try:
        current_time = datetime.now(timezone.utc).timestamp()
        last_update = st.session_state.last_metrics_update.get(entity_id, 0)
        
        # Prevent updates more frequently than every 5 seconds
        if (current_time - last_update) < 5:
            logger.info(f"Update for {entity_id} skipped - too soon since last update")
            return False, 0

        # Check update locks
        if st.session_state.get('update_in_progress') or st.session_state.get(f'update_lock_{entity_id}'):
            logger.info(f"Update already in progress for {entity_id}")
            return False, 0

        # Set locks
        st.session_state.update_in_progress = True
        st.session_state[f'update_lock_{entity_id}'] = True
        
        try:
            progress_bar.progress(0.2, "Initializing update...")
            success, summary = update_entity_metrics(entity_type, entity_id)
            
            if success:
                progress_bar.progress(0.8, "Generating updated reports...")
                # Update timestamps and clear caches
                st.session_state.last_metrics_update[entity_id] = current_time
                st.session_state.metrics_cache.pop(entity_id, None)
                st.session_state.current_metrics.pop(entity_id, None)
                st.session_state.project_metrics.pop(entity_id, None)
                st.session_state.historical_data.pop(entity_id, None)

                # Generate and send reports after successful update
                report_generator = ReportGenerator()
                daily_report = report_generator.generate_daily_report(entity_id)
                if daily_report:
                    recipients = report_generator.get_report_recipients('daily')
                    if recipients:
                        report_generator.send_email(
                            recipients,
                            "Daily SonarCloud Metrics Report (Auto-Update)",
                            daily_report,
                            'HTML'
                        )

                weekly_report = report_generator.generate_weekly_report(entity_id)
                if weekly_report:
                    recipients = report_generator.get_report_recipients('weekly')
                    if recipients:
                        report_generator.send_email(
                            recipients,
                            "Weekly SonarCloud Metrics Report (Auto-Update)",
                            weekly_report,
                            'HTML'
                        )

                progress_bar.progress(1.0, "✅ Update and reports completed!")
                st.rerun()
                return True, summary.get('updated_count', 0)
            else:
                error_msg = summary.get('errors', ['Unknown error'])[0]
                progress_bar.progress(1.0, f"❌ Update failed: {error_msg}")
                return False, 0
                
        finally:
            # Always release locks
            st.session_state.update_in_progress = False
            st.session_state[f'update_lock_{entity_id}'] = False
            
    except Exception as e:
        logger.error(f"Error during update for {entity_id}: {str(e)}")
        progress_bar.progress(1.0, f"❌ Error during update: {str(e)}")
        # Ensure locks are released
        st.session_state.update_in_progress = False
        st.session_state[f'update_lock_{entity_id}'] = False
        return False, 0

def main():
    try:
        st.set_page_config(
            page_title="SonarCloud Metrics Dashboard",
            page_icon="📊",
            layout="wide",
            initial_sidebar_state="expanded"
        )

        # Reset pending rerun flag at the start of each session
        if st.session_state.get('pending_rerun'):
            st.session_state.pending_rerun = False

        initialize_session_state()
        initialize_database()
        
        scheduler = SchedulerService()
        if not scheduler.scheduler.running:
            logger.info("Starting scheduler service")
            scheduler.start()

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
                show_inactive = st.checkbox(
                    "Show Inactive Projects",
                    value=st.session_state.show_inactive_projects
                )
                
                if show_inactive != st.session_state.show_inactive_projects:
                    st.session_state.show_inactive_projects = show_inactive
                    st.session_state.metrics_cache = {}
                    st.session_state.project_metrics = {}
                    st.rerun()  # Use safe rerun instead of direct rerun

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
                # Clear project-specific caches
                st.session_state.metrics_cache.pop(selected_project, None)
                st.session_state.current_metrics.pop(selected_project, None)
                st.session_state.project_metrics.pop(selected_project, None)
                st.session_state.historical_data.pop(selected_project, None)
                st.session_state.previous_project = selected_project

            if selected_project == 'all':
                st.markdown("## 📊 All Projects Overview")

                st.markdown("### 🔄 Update Status")
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
                            progress_bar.progress(0.8, "Generating updated reports...")
                            st.session_state.metrics_cache = projects_data
                            
                            # Generate and send reports after successful update
                            report_generator = ReportGenerator()
                            daily_report = report_generator.generate_daily_report()
                            weekly_report = report_generator.generate_weekly_report()
                            
                            if daily_report:
                                recipients = report_generator.get_report_recipients('daily')
                                if recipients:
                                    report_generator.send_email(
                                        recipients,
                                        "Daily SonarCloud Metrics Report (Auto-Update)",
                                        daily_report,
                                        'HTML'
                                    )
                            
                            if weekly_report:
                                recipients = report_generator.get_report_recipients('weekly')
                                if recipients:
                                    report_generator.send_email(
                                        recipients,
                                        "Weekly SonarCloud Metrics Report (Auto-Update)",
                                        weekly_report,
                                        'HTML'
                                    )
                            
                            progress_bar.progress(1.0, f"✅ Updated {len(projects_data)} projects and generated reports")
                            st.success(f"Updated {len(projects_data)} projects from SonarCloud")
                            st.rerun()
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
                project_info = project_status.get(selected_project, {})
                st.markdown(f"## 📊 Project Dashboard: {project_names[selected_project]}")
                
                is_inactive = not project_info.get('is_active', True)
                
                if not is_inactive:
                    col1, col2 = st.columns([3, 1])
                    with col2:
                        current_time = datetime.now(timezone.utc).timestamp()
                        last_update = st.session_state.last_metrics_update.get(selected_project, 0)
                        
                        update_enabled = (
                            (current_time - last_update) > 5 and 
                            not st.session_state.update_in_progress and
                            not st.session_state.get(f'update_lock_{selected_project}')
                        )
                        
                        if st.button("🔄 Update Metrics", 
                                  use_container_width=True, 
                                  disabled=not update_enabled):
                            progress_bar = st.progress(0, "Starting update...")
                            success, updated_count = manual_update_metrics(
                                'repository', 
                                selected_project,
                                progress_bar
                            )
                
                metrics_tabs = st.tabs(["📊 Current Metrics", "📈 Metric Trends"])
                
                with metrics_tabs[0]:  # Current Metrics tab
                    try:
                        if selected_project not in st.session_state.current_metrics:
                            metrics = metrics_processor.get_latest_metrics(selected_project)
                            if metrics:
                                metrics_dict = {k: float(v) for k, v in metrics.items() 
                                            if k not in ['timestamp', 'last_seen', 'is_active', 'inactive_duration']}
                                st.session_state.current_metrics[selected_project] = metrics_dict
                                display_current_metrics(metrics_dict)
                                
                                # Display update preferences
                                update_prefs = get_update_preferences('repository', selected_project)
                                if update_prefs:
                                    st.markdown("---")
                                    col1, col2 = st.columns(2)
                                    with col1:
                                        st.info(f"🔄 Update Interval: {format_update_interval(update_prefs['update_interval'])}")
                                    with col2:
                                        if update_prefs['last_update']:
                                            st.info(f"⏰ Last Update: {format_last_update(update_prefs['last_update'])}")
                    except Exception as e:
                        logger.error(f"Error displaying metrics for {selected_project}: {str(e)}")
                        st.error(f"Error displaying metrics: {str(e)}")

                with metrics_tabs[1]:  # Metric Trends tab
                    try:
                        if selected_project not in st.session_state.historical_data:
                            historical_data = metrics_processor.get_historical_data(selected_project)
                            if historical_data:
                                st.session_state.historical_data[selected_project] = historical_data
                        
                        if selected_project in st.session_state.historical_data:
                            historical_data = st.session_state.historical_data[selected_project]
                            if historical_data:
                                plot_metrics_history(historical_data)
                                display_metric_trends(historical_data)
                            else:
                                st.info("No historical data available for trend analysis")
                    except Exception as e:
                        logger.error(f"Error displaying trends for {selected_project}: {str(e)}")
                        st.error(f"Error displaying trends: {str(e)}")

    except Exception as e:
        logger.error(f"Main application error: {str(e)}", exc_info=True)
        st.error(f"An error occurred: {str(e)}")

if __name__ == "__main__":
    main()