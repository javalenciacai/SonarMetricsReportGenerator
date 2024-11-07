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

def get_all_projects_data():
    """Get all projects data from database with latest metrics"""
    query = """
    WITH LatestMetrics AS (
        SELECT 
            repository_id,
            bugs,
            vulnerabilities,
            code_smells,
            coverage,
            duplicated_lines_density,
            ncloc,
            sqale_index,
            timestamp AT TIME ZONE 'UTC' as timestamp,
            ROW_NUMBER() OVER (PARTITION BY repository_id ORDER BY timestamp DESC) as rn
        FROM metrics
    )
    SELECT 
        r.repo_key,
        r.name,
        r.is_active,
        r.is_marked_for_deletion,
        r.update_interval,
        r.last_seen AT TIME ZONE 'UTC' as last_seen,
        m.bugs,
        m.vulnerabilities,
        m.code_smells,
        m.coverage,
        m.duplicated_lines_density,
        m.ncloc,
        m.sqale_index,
        m.timestamp
    FROM repositories r
    LEFT JOIN LatestMetrics m ON m.repository_id = r.id AND m.rn = 1
    ORDER BY 
        r.is_active DESC,
        r.name ASC;
    """
    
    try:
        result = execute_query(query)
        projects_data = {}
        
        for row in result:
            project_data = dict(row)
            project_key = project_data['repo_key']
            
            # Format project name with status and proper spacing
            if project_data['is_marked_for_deletion']:
                status_indicator = '🗑️\u00A0'  # Using non-breaking space
            elif not project_data['is_active']:
                status_indicator = '⚠️\u00A0'
            else:
                status_indicator = '✅\u00A0'
            
            formatted_name = f"{status_indicator}{project_data['name']}"
            
            # Always include project data with formatted name
            projects_data[project_key] = {
                'name': formatted_name,
                'display_name': project_data['name'],  # Original name without status
                'is_active': project_data['is_active'],
                'is_marked_for_deletion': project_data['is_marked_for_deletion'],
                'update_interval': project_data['update_interval'],
                'last_seen': project_data['last_seen'],
                'metrics': None  # Initialize metrics as None
            }
            
            # Add metrics if they exist
            if project_data['bugs'] is not None:
                projects_data[project_key]['metrics'] = {
                    'bugs': float(project_data['bugs']),
                    'vulnerabilities': float(project_data['vulnerabilities']),
                    'code_smells': float(project_data['code_smells']),
                    'coverage': float(project_data['coverage']),
                    'duplicated_lines_density': float(project_data['duplicated_lines_density']),
                    'ncloc': float(project_data['ncloc']),
                    'sqale_index': float(project_data['sqale_index']),
                    'timestamp': project_data['timestamp']
                }
                logger.info(f"Retrieved metrics for project: {project_key}")
            else:
                logger.info(f"No metrics available for project: {project_key}")
        
        return projects_data
        
    except Exception as e:
        logger.error(f"Error retrieving project data: {str(e)}")
        return {}

def sync_all_projects():
    try:
        # Initialize and validate SonarCloud API first
        sonar_api = SonarCloudAPI(os.getenv('SONARCLOUD_TOKEN'))
        is_valid, message = sonar_api.validate_token()
        if not is_valid:
            return False, message

        # Set organization before continuing
        organization = sonar_api.get_organization()
        if not organization:
            return False, "Organization not set or invalid"
        sonar_api.organization = organization

        # Continue with fetching and updating projects
        query = '''
        SELECT repo_key
        FROM repositories
        WHERE is_active = true AND is_marked_for_deletion = false;
        '''
        result = execute_query(query)
        if not result:
            return False, 'No active projects found'
        
        success_count = 0
        failed_count = 0
        
        for row in result:
            try:
                success = update_entity_metrics('repository', row[0])
                if success:
                    success_count += 1
                else:
                    failed_count += 1
            except Exception as e:
                logger.error(f'Error updating project {row[0]}: {str(e)}')
                failed_count += 1
        
        return True, f'Updated {success_count} projects successfully, {failed_count} failed'
    except Exception as e:
        logger.error(f'Error in sync_all_projects: {str(e)}')
        return False, str(e)

def main():
    try:
        st.set_page_config(
            page_title="SonarCloud Metrics Dashboard",
            page_icon="📊",
            layout="wide",
            initial_sidebar_state="expanded"
        )

        # Add custom CSS for dark mode styling
        st.markdown("""
            <style>
            /* Dark mode styles */
            .stSelectbox div[data-baseweb="select"] {
                background-color: #1E2530 !important;
                border-color: #2D3748 !important;
            }
            
            .stSelectbox div[data-baseweb="select"]:hover {
                border-color: #4A5568 !important;
            }
            
            .stSelectbox div[data-baseweb="select"] div {
                color: #E2E8F0 !important;
            }
            
            .stSelectbox div[data-baseweb="select"] [role="listbox"] {
                background-color: #1E2530 !important;
                border-color: #2D3748 !important;
            }
            
            .stSelectbox div[data-baseweb="select"] [role="option"] {
                background-color: #1E2530 !important;
                color: #E2E8F0 !important;
                padding: 8px 12px !important;
            }
            
            .stSelectbox div[data-baseweb="select"] [role="option"]:hover {
                background-color: #2D3748 !important;
            }
            
            /* Project status indicators with improved spacing */
            .stSelectbox div[data-baseweb="select"] [role="option"] {
                display: flex !important;
                align-items: center !important;
                gap: 8px !important;
            }
            
            .stSelectbox div[data-baseweb="select"] [role="option"] span {
                display: inline-flex !important;
                align-items: center !important;
                color: #E2E8F0 !important;
            }
            
            /* Status indicator colors */
            .project-status-active {
                color: #48BB78 !important;
                margin-right: 8px !important;
            }
            
            .project-status-inactive {
                color: #ECC94B !important;
                margin-right: 8px !important;
            }
            
            .project-status-deletion {
                color: #F56565 !important;
                margin-right: 8px !important;
            }
            
            /* Selected option styling */
            .stSelectbox div[data-baseweb="select"] [aria-selected="true"] {
                background-color: #2D3748 !important;
            }
            
            /* Dropdown arrow color */
            .stSelectbox div[data-baseweb="select"] svg {
                color: #A0AEC0 !important;
            }
            
            /* Checkbox styling */
            .stCheckbox label {
                color: #E2E8F0 !important;
            }
            
            .stCheckbox label:hover {
                color: #FFFFFF !important;
            }
            </style>
        """, unsafe_allow_html=True)

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
            all_projects_data = get_all_projects_data()
            
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

            # Filter projects based on active/inactive status
            filtered_projects = {k: v for k, v in all_projects_data.items()}
            if not show_inactive:
                filtered_projects = {k: v for k, v in filtered_projects.items() 
                                  if v['is_active'] or k == 'all'}

            # Add "All Projects" option
            filtered_projects['all'] = {
                'name': "📊 All Projects",
                'display_name': "All Projects",
                'is_active': True,
                'metrics': None
            }

            selected_project = st.sidebar.selectbox(
                "Select Project",
                options=list(filtered_projects.keys()),
                format_func=lambda x: filtered_projects[x]['name'],
                key='selected_project'
            )

            if selected_project == 'all':
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.markdown("## 📊 All Projects Overview")
                with col2:
                    if st.button("🔄 Sync All Projects", help="Trigger an immediate update for all active projects"):
                        with st.spinner("Syncing all projects..."):
                            success, message = sync_all_projects()
                            if success:
                                st.success(f"✅ {message}")
                            else:
                                st.error(f"❌ Sync failed: {message}")
                
                if filtered_projects:
                    display_multi_project_metrics(filtered_projects)
                    plot_multi_project_comparison(filtered_projects)
                    create_download_report(filtered_projects)
                else:
                    st.info("No projects data available")
            
            elif selected_project:
                project_info = filtered_projects.get(selected_project, {})
                st.markdown(f"## 📊 Project Dashboard: {project_info['display_name']}")
                
                is_inactive = not project_info.get('is_active', True)
                
                current_tab, trends_tab = st.tabs(["📊 Current Metrics", "📈 Metric Trends"])
                
                with current_tab:
                    metrics = project_info.get('metrics')
                    if metrics:
                        display_current_metrics(metrics)
                        if not is_inactive:
                            create_download_report({selected_project: project_info})
                    else:
                        st.warning("No metrics available for this project")

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
