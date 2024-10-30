import streamlit as st
import os
from services.sonarcloud import SonarCloudAPI
from services.metrics_processor import MetricsProcessor
from services.scheduler import SchedulerService
from services.report_generator import ReportGenerator
from services.notification_service import NotificationService
from services.metrics_updater import update_entity_metrics
from components.metrics_display import display_current_metrics, create_download_report, display_metric_trends, display_multi_project_metrics
from components.visualizations import plot_metrics_history, plot_multi_project_comparison
from components.policy_display import show_policies, get_policy_acceptance_status
from components.group_management import manage_project_groups
from components.interval_settings import display_interval_settings
from database.schema import initialize_database

scheduler = SchedulerService()
report_generator = None
notification_service = None

def handle_project_switch():
    """Handle project selection changes without unnecessary refreshes"""
    if 'previous_project' in st.session_state:
        if st.session_state.get('previous_project') != st.session_state.get('selected_project'):
            st.session_state.show_inactive = False
            st.session_state.previous_project = st.session_state.selected_project

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

def handle_interval_update():
    """Handle update interval changes"""
    if hasattr(st.session_state, 'update_interval_changed') and st.session_state.update_interval_changed:
        new_interval = st.session_state.new_interval
        scheduler.schedule_metrics_update(
            update_entity_metrics,
            new_interval['entity_type'],
            new_interval['entity_id'],
            new_interval['interval']
        )
        # Reset the state
        st.session_state.update_interval_changed = False
        st.session_state.new_interval = None
        st.rerun()

def main():
    try:
        st.set_page_config(
            page_title="SonarCloud Metrics Dashboard",
            page_icon="📊",
            layout="wide",
            initial_sidebar_state="expanded"
        )

        # Initialize session state
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
            st.session_state.update_interval_changed = False
            st.session_state.new_interval = None

        initialize_database()
        
        global report_generator, notification_service

        if not scheduler.scheduler.running:
            scheduler.start()

        # Handle any pending interval updates
        handle_interval_update()

        sidebar = setup_sidebar()

        # Sidebar navigation with form to prevent unnecessary refreshes
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
            active_projects = sonar_api.get_projects()
            
            all_projects_status = metrics_processor.get_project_status()
            project_names = {}

            for project in active_projects:
                project_names[project['key']] = f"✅ {project['name']}"
            
            for project in all_projects_status:
                if not project['is_active']:
                    deletion_mark = "🗑️" if project.get('is_marked_for_deletion') else "⚠️"
                    project_names[project['repo_key']] = f"{deletion_mark} {project['name']} (Inactive)"
            
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
                key='selected_project',
                on_change=handle_project_switch
            )

            if selected_project == 'all':
                st.markdown("## 📊 All Projects Overview")
                projects_data = {}
                for project in active_projects:
                    metrics = sonar_api.get_project_metrics(project['key'])
                    if metrics:
                        metrics_dict = {m['metric']: float(m['value']) for m in metrics}
                        projects_data[project['key']] = {
                            'name': project['name'],
                            'metrics': metrics_dict
                        }
                
                if projects_data:
                    display_multi_project_metrics(projects_data)
                    plot_multi_project_comparison(projects_data)
                    create_download_report(projects_data)
            
            elif selected_project:
                st.markdown(f"## 📊 Project Dashboard: {project_names[selected_project]}")
                
                is_inactive = '⚠️' in project_names[selected_project] or '🗑️' in project_names[selected_project]
                
                if is_inactive:
                    handle_inactive_project(selected_project, metrics_processor)
                
                metrics = None
                try:
                    metrics = sonar_api.get_project_metrics(selected_project)
                except Exception as e:
                    if is_inactive:
                        st.info("Using historical data for inactive project")
                        project_data = metrics_processor.get_latest_metrics(selected_project)
                        if project_data:
                            metrics_dict = {k: float(v) for k, v in project_data.items() 
                                         if k not in ['timestamp', 'last_seen', 'is_active', 'inactive_duration']}
                            display_current_metrics(metrics_dict)
                            
                            historical_data = metrics_processor.get_historical_data(selected_project)
                            if historical_data:
                                plot_metrics_history(historical_data)
                                display_metric_trends(historical_data)
                                create_download_report(historical_data)
                    else:
                        st.error(f"Failed to fetch metrics: {str(e)}")
                
                if metrics:
                    metrics_dict = {m['metric']: float(m['value']) for m in metrics}
                    metrics_processor.store_metrics(selected_project, 
                                                 project_names[selected_project].split(" ")[1], 
                                                 metrics_dict)
                    display_current_metrics(metrics_dict)
                    
                    historical_data = metrics_processor.get_historical_data(selected_project)
                    if historical_data:
                        plot_metrics_history(historical_data)
                        display_metric_trends(historical_data)
                        create_download_report(historical_data)

                if selected_project != 'all' and not is_inactive:
                    st.sidebar.markdown("---")
                    with st.sidebar:
                        display_interval_settings(
                            'repository',
                            selected_project,
                            scheduler
                        )

    except Exception as e:
        st.error(f"Application error: {str(e)}")

if __name__ == "__main__":
    main()