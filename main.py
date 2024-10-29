import streamlit as st
from services.sonarcloud import SonarCloudAPI
from services.metrics_processor import MetricsProcessor
from services.scheduler import SchedulerService
from services.report_generator import ReportGenerator
from services.notification_service import NotificationService
from components.metrics_display import display_current_metrics, create_download_report, display_metric_trends, display_multi_project_metrics
from components.visualizations import plot_metrics_history, plot_multi_project_comparison
from components.policy_display import show_policies, get_policy_acceptance_status
from components.project_groups import manage_project_groups, get_group_metrics
from database.schema import initialize_database
import os
from datetime import datetime, timedelta

scheduler = SchedulerService()
report_generator = None
notification_service = None

def reset_project_state():
    """Reset project state and clear group cache"""
    st.session_state.selected_project = 'all'
    if 'group_cache' in st.session_state:
        del st.session_state.group_cache

def get_cached_metrics(sonar_api, project_key, force_refresh=False):
    """Get metrics with caching"""
    cache_key = f"metrics_{project_key}"
    cache_valid = (
        cache_key in st.session_state and
        st.session_state[cache_key]['timestamp'] > datetime.now() - timedelta(minutes=5)
    )
    
    if not cache_valid or force_refresh:
        metrics = sonar_api.get_project_metrics(project_key)
        if metrics:
            metrics_dict = {m['metric']: float(m['value']) for m in metrics}
            st.session_state[cache_key] = {
                'data': metrics_dict,
                'timestamp': datetime.now()
            }
            return metrics_dict
        return None
    
    return st.session_state[cache_key]['data']

def main():
    try:
        st.set_page_config(
            page_title="SonarCloud Metrics Dashboard",
            page_icon="📊",
            layout="wide",
            initial_sidebar_state="expanded"
        )

        # Initialize session state
        if 'selected_project' not in st.session_state:
            st.session_state.selected_project = 'all'
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

        sidebar = st.sidebar
        with sidebar:
            st.markdown("""
                <div style="display: flex; justify-content: center; margin-bottom: 1rem;">
                    <img src="static/sonarcloud-logo.svg" alt="SonarCloud Logo" style="width: 180px; height: auto;">
                </div>
            """, unsafe_allow_html=True)
            st.markdown("---")
        
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

        with sidebar:
            st.markdown("### 🎯 Project Selection")
            
            new_project = st.selectbox(
                "Select Project",
                options=['all'] + list(project_names.keys())[:-1],
                format_func=lambda x: project_names[x],
                key="project_selector"
            )

            if new_project != st.session_state.selected_project:
                st.session_state.selected_project = new_project
                reset_project_state()

        if st.session_state.selected_project == 'all':
            st.markdown("## 📊 Multi-Project Overview")
            
            # Add refresh button for all projects
            if st.button("🔄 Refresh All Metrics"):
                st.session_state.refresh_metrics = True
                
            tab1, tab2 = st.tabs(["📊 All Projects", "📁 Project Groups"])
            
            with tab1:
                show_inactive = st.checkbox(
                    "🔍 Show Inactive Projects",
                    value=st.session_state.show_inactive_projects,
                    help="Toggle to show/hide inactive projects in the overview",
                    key="inactive_projects_filter"
                )
                st.session_state.show_inactive_projects = show_inactive
                
                all_project_metrics = {}
                force_refresh = st.session_state.get('refresh_metrics', False)
                
                for project_key in active_project_keys:
                    metrics_dict = get_cached_metrics(sonar_api, project_key, force_refresh)
                    if metrics_dict:
                        all_project_metrics[project_key] = {
                            'name': project_names[project_key].replace('✅ ', ''),
                            'metrics': metrics_dict
                        }
                        MetricsProcessor.store_metrics(project_key, project_names[project_key], metrics_dict)
                
                if show_inactive:
                    for project in all_projects_status:
                        if not project['is_active']:
                            latest_metrics = project.get('latest_metrics')
                            if latest_metrics:
                                metrics_dict = {
                                    'bugs': float(latest_metrics['bugs']),
                                    'vulnerabilities': float(latest_metrics['vulnerabilities']),
                                    'code_smells': float(latest_metrics['code_smells']),
                                    'coverage': float(latest_metrics['coverage']),
                                    'duplicated_lines_density': float(latest_metrics['duplicated_lines_density']),
                                    'ncloc': float(latest_metrics['ncloc']),
                                    'sqale_index': float(latest_metrics['sqale_index'])
                                }
                                all_project_metrics[project['repo_key']] = {
                                    'name': f"{project['name']} (Inactive)",
                                    'metrics': metrics_dict,
                                    'is_inactive': True
                                }

                # Reset refresh flag
                if force_refresh:
                    st.session_state.refresh_metrics = False

                if all_project_metrics:
                    display_multi_project_metrics(all_project_metrics)
                    plot_multi_project_comparison(all_project_metrics)
                else:
                    if show_inactive:
                        st.warning("No projects found (active or inactive)")
                    else:
                        st.warning("No active projects found")
            
            with tab2:
                manage_project_groups(active_projects, project_names)

        else:
            try:
                is_inactive = st.session_state.selected_project not in active_project_keys
                
                if not is_inactive:
                    # Add refresh button for single project
                    if st.button("🔄 Refresh Metrics"):
                        st.session_state.refresh_metrics = True
                    
                    metrics_dict = get_cached_metrics(
                        sonar_api,
                        st.session_state.selected_project,
                        force_refresh=st.session_state.get('refresh_metrics', False)
                    )
                    
                    if metrics_dict:
                        MetricsProcessor.store_metrics(
                            st.session_state.selected_project,
                            project_names[st.session_state.selected_project],
                            metrics_dict
                        )
                        
                        # Reset refresh flag
                        if st.session_state.get('refresh_metrics'):
                            st.session_state.refresh_metrics = False
                        
                        tab1, tab2 = st.tabs(["📊 Executive Dashboard", "📈 Trend Analysis"])
                        
                        with tab1:
                            display_current_metrics(metrics_dict)
                        
                        with tab2:
                            historical_data = MetricsProcessor.get_historical_data(st.session_state.selected_project)
                            if historical_data:
                                display_metric_trends(historical_data)
                                create_download_report(historical_data)
                            else:
                                st.warning("⚠️ No historical data available for trend analysis")
                
                else:
                    st.warning(f"⚠️ This project is currently inactive. Showing historical data only.")
                    
                    latest_metrics = metrics_processor.get_latest_metrics(st.session_state.selected_project)
                    if latest_metrics:
                        tab1, tab2 = st.tabs(["📊 Last Available Metrics", "📈 Historical Data"])
                        
                        with tab1:
                            st.info(f"⏰ Last updated: {latest_metrics['last_seen']}")
                            st.info(f"⌛ Inactive for: {latest_metrics['inactive_duration'].days} days")
                            
                            metrics_dict = {
                                'bugs': float(latest_metrics['bugs']),
                                'vulnerabilities': float(latest_metrics['vulnerabilities']),
                                'code_smells': float(latest_metrics['code_smells']),
                                'coverage': float(latest_metrics['coverage']),
                                'duplicated_lines_density': float(latest_metrics['duplicated_lines_density']),
                                'ncloc': float(latest_metrics['ncloc']),
                                'sqale_index': float(latest_metrics['sqale_index'])
                            }
                            display_current_metrics(metrics_dict)
                        
                        with tab2:
                            historical_data = metrics_processor.get_historical_data(st.session_state.selected_project)
                            if historical_data:
                                plot_metrics_history(historical_data)
                                display_metric_trends(historical_data)
                                create_download_report(historical_data)
                    else:
                        st.info("No historical data available for this inactive project.")
                
            except Exception as e:
                st.error(f"Error displaying project data: {str(e)}")
                reset_project_state()

    except Exception as e:
        st.error(f"Application error: {str(e)}")
        reset_project_state()

if __name__ == "__main__":
    main()
