import streamlit as st
from services.sonarcloud import SonarCloudAPI
from services.metrics_processor import MetricsProcessor
from services.scheduler import SchedulerService
from services.report_generator import ReportGenerator
from services.notification_service import NotificationService
from components.metrics_display import display_current_metrics, create_download_report, display_metric_trends, display_multi_project_metrics
from components.visualizations import plot_metrics_history, plot_multi_project_comparison
from components.policy_display import show_policies, get_policy_acceptance_status
from components.group_management import manage_project_groups
from components.interval_settings import display_interval_settings
from database.schema import initialize_database
import os
from datetime import datetime, timedelta

scheduler = SchedulerService()
report_generator = None
notification_service = None

def update_entity_metrics(entity_type, entity_id):
    """Update metrics for an entity (project or group)"""
    try:
        sonar_api = SonarCloudAPI(st.session_state.sonar_token)
        metrics_processor = MetricsProcessor()
        
        if entity_type == 'repository':
            metrics = sonar_api.get_project_metrics(entity_id)
            if metrics:
                metrics_dict = {m['metric']: float(m['value']) for m in metrics}
                MetricsProcessor.store_metrics(entity_id, "", metrics_dict)
        elif entity_type == 'group':
            projects = metrics_processor.get_projects_in_group(entity_id)
            for project in projects:
                metrics = sonar_api.get_project_metrics(project['repo_key'])
                if metrics:
                    metrics_dict = {m['metric']: float(m['value']) for m in metrics}
                    MetricsProcessor.store_metrics(project['repo_key'], project['name'], metrics_dict)
    except Exception as e:
        print(f"Error updating metrics for {entity_type} {entity_id}: {str(e)}")

def setup_sidebar():
    with st.sidebar:
        st.markdown("""
            <div style="display: flex; justify-content: center; margin-bottom: 1rem;">
                <img src="static/sonarcloud-logo.svg" alt="SonarCloud Logo" style="width: 180px; height: auto;">
            </div>
        """, unsafe_allow_html=True)
        st.markdown("---")
        return st.sidebar

def reset_project_state():
    st.session_state.show_inactive = False
    st.session_state.previous_project = st.session_state.get('selected_project')

def handle_project_switch():
    if st.session_state.get('previous_project') != st.session_state.get('selected_project'):
        reset_project_state()

def main():
    try:
        st.set_page_config(
            page_title="SonarCloud Metrics Dashboard",
            page_icon="📊",
            layout="wide",
            initial_sidebar_state="expanded"
        )

        # Initialize session state
        if 'policies_accepted' not in st.session_state:
            st.session_state.policies_accepted = False
        if 'selected_project' not in st.session_state:
            st.session_state.selected_project = None
        if 'selected_group' not in st.session_state:
            st.session_state.selected_group = None
        if 'show_inactive' not in st.session_state:
            st.session_state.show_inactive = False
        if 'previous_project' not in st.session_state:
            st.session_state.previous_project = None
        if 'show_inactive_projects' not in st.session_state:
            st.session_state.show_inactive_projects = True
        if 'sonar_token' not in st.session_state:
            st.session_state.sonar_token = None

        initialize_database()
        
        global report_generator, notification_service

        if not scheduler.scheduler.running:
            scheduler.start()

        sidebar = setup_sidebar()

        with sidebar:
            st.markdown("### 📊 Navigation")
            view_mode = st.radio(
                "Select View",
                ["Individual Projects", "Project Groups"],
                key="view_mode"
            )
        
        token = os.getenv('SONARCLOUD_TOKEN') or st.text_input("Enter SonarCloud Token", type="password")
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
            # Add interval settings for currently selected group
            if st.session_state.get('selected_group'):
                st.sidebar.markdown("---")
                with st.sidebar:
                    display_interval_settings(
                        'group',
                        st.session_state.selected_group,
                        scheduler
                    )
        else:
            active_projects = sonar_api.get_projects()
            if not active_projects:
                st.warning("No active projects found in the organization")
                return
            
            active_project_keys = [project['key'] for project in active_projects] if active_projects else []
            all_projects_status = metrics_processor.get_project_status()
            
            project_names = {}
            if active_projects:
                for project in active_projects:
                    project_names[project['key']] = f"✅ {project['name']}"
            
            for project in all_projects_status:
                if not project['is_active']:
                    project_names[project['repo_key']] = f"⚠️ {project['name']} (Inactive)"
            
            project_names['all'] = "📊 All Projects"
            
            # Rest of the existing code for project view...
            if st.session_state.selected_project != 'all':
                st.sidebar.markdown("---")
                with st.sidebar:
                    display_interval_settings(
                        'repository',
                        st.session_state.selected_project,
                        scheduler
                    )

    except Exception as e:
        st.error(f"Application error: {str(e)}")
        reset_project_state()

if __name__ == "__main__":
    main()
