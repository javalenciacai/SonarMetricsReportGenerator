import streamlit as st
from services.sonarcloud import SonarCloudAPI
from services.metrics_processor import MetricsProcessor
from services.scheduler import SchedulerService
from services.report_generator import ReportGenerator
from services.notification_service import NotificationService
from components.metrics_display import display_current_metrics, create_download_report, display_metric_trends, display_multi_project_metrics
from components.visualizations import plot_metrics_history, plot_multi_project_comparison
from components.policy_display import show_policies, get_policy_acceptance_status
from components.tag_management import display_project_tags, display_tag_management
from database.schema import initialize_database
import os
from datetime import datetime, timedelta

scheduler = SchedulerService()
report_generator = None
notification_service = None

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

def display_project_management(metrics_processor, active_project_keys):
    with st.sidebar:
        st.markdown("### 🔧 Project Management")
        
        projects_status = metrics_processor.get_project_status()
        
        if projects_status:
            if active_project_keys:
                metrics_processor.check_and_mark_inactive_projects(active_project_keys)
            
            inactive_projects = [p for p in projects_status if not p['is_active']]
            active_projects = [p for p in projects_status if p['is_active']]
            
            st.success(f"✅ {len(active_projects)} active project(s)")
            
            if inactive_projects:
                st.warning(f"⚠️ {len(inactive_projects)} inactive project(s)")
                
                for project in inactive_projects:
                    with st.expander(f"📁 {project['name']} (Inactive)", expanded=False):
                        st.text(f"Last seen: {project['last_seen'].strftime('%Y-%m-%d')}")
                        st.text(f"Inactive for: {project['inactive_duration'].days} days")
                        st.markdown("ℹ️ *This project is no longer found in SonarCloud*")
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            if not project.get('is_marked_for_deletion'):
                                if st.button("🗑️ Mark for Deletion", key=f"mark_{project['repo_key']}"):
                                    success, message = metrics_processor.mark_project_for_deletion(project['repo_key'])
                                    if success:
                                        st.success(message)
                                        st.rerun()
                                    else:
                                        st.error(message)
                            else:
                                st.info("🗑️ Marked for deletion")
                                if st.button("↩️ Unmark Deletion", key=f"unmark_{project['repo_key']}"):
                                    success, message = metrics_processor.unmark_project_for_deletion(project['repo_key'])
                                    if success:
                                        st.success(message)
                                        st.rerun()
                                    else:
                                        st.error(message)
                        
                        with col2:
                            if project.get('is_marked_for_deletion'):
                                if st.button("⚠️ Delete Data", key=f"delete_{project['repo_key']}", 
                                           help="Warning: This will permanently delete all project data!"):
                                    success, message = metrics_processor.delete_project_data(project['repo_key'])
                                    if success:
                                        st.success(message)
                                        st.rerun()
                                    else:
                                        st.error(message)
                        
                        if st.button(f"📊 View Historical Data", key=f"hist_{project['repo_key']}"):
                            st.session_state.selected_project = project['repo_key']
                            st.session_state.show_inactive = True
                            st.rerun()
            else:
                st.success("✅ No inactive projects")

def main():
    try:
        st.set_page_config(
            page_title="SonarCloud Metrics Dashboard",
            page_icon="📊",
            layout="wide",
            initial_sidebar_state="expanded"
        )

        if 'policies_accepted' not in st.session_state:
            st.session_state.policies_accepted = False
        if 'selected_project' not in st.session_state:
            st.session_state.selected_project = None
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
        
        display_project_management(metrics_processor, active_project_keys)
        
        with sidebar:
            st.markdown("### 🎯 Project Selection")
            
            new_project = st.selectbox(
                "Select Project",
                options=['all'] + list(project_names.keys())[:-1],
                format_func=lambda x: project_names[x],
                key="project_selector"
            )

            if new_project != st.session_state.get('selected_project'):
                st.session_state.selected_project = new_project
                handle_project_switch()

            st.markdown("---")

            if st.session_state.selected_project != 'all' and st.session_state.selected_project in active_project_keys:
                st.markdown("### ⚙️ Automation Setup")
                
                try:
                    smtp_status, smtp_message = report_generator.verify_smtp_connection()
                    if smtp_status:
                        st.success("✉️ Email Configuration: Connected")
                    else:
                        st.error(f"✉️ Email Configuration: {smtp_message}")
                except Exception as e:
                    st.error(f"✉️ Email Configuration Error: {str(e)}")
                
                email_recipients = st.text_input(
                    "📧 Email Recipients",
                    help="Enter email addresses (comma-separated) to receive reports and notifications"
                )

                if email_recipients:
                    if st.button("🔄 Setup Automation"):
                        recipients_list = [email.strip() for email in email_recipients.split(",")]
                        
                        with st.spinner("⏳ Testing report generation and email sending..."):
                            report_data, gen_message = report_generator.generate_project_report(st.session_state.selected_project, 'daily')
                            if report_data:
                                success, send_message = report_generator.send_report_email(report_data, recipients_list)
                                if success:
                                    if setup_automated_reports(sonar_api, st.session_state.selected_project, recipients_list):
                                        st.success("""
                                            ✅ Setup successful!
                                            - 📧 Test email sent
                                            - 📅 Daily reports: 1:00 AM
                                            - 📅 Weekly reports: Monday 2:00 AM
                                            - 🔔 Change notifications: Every 4 hours
                                        """)
                                else:
                                    st.error(f"❌ Failed to send test email: {send_message}")
                            else:
                                st.error(f"❌ Failed to generate test report: {gen_message}")

        if st.session_state.selected_project == 'all':
            st.markdown("## 📊 Multi-Project Overview")
            
            show_inactive = st.checkbox(
                "🔍 Show Inactive Projects",
                value=st.session_state.show_inactive_projects,
                help="Toggle to show/hide inactive projects in the overview",
                key="inactive_projects_filter"
            )
            st.session_state.show_inactive_projects = show_inactive
            
            all_project_metrics = {}
            
            for project_key in active_project_keys:
                metrics = sonar_api.get_project_metrics(project_key)
                if metrics:
                    metrics_dict = {m['metric']: float(m['value']) for m in metrics}
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

            if all_project_metrics:
                display_multi_project_metrics(all_project_metrics)
                plot_multi_project_comparison(all_project_metrics)
                st.markdown("---")
                display_tag_management()
            else:
                if show_inactive:
                    st.warning("No projects found (active or inactive)")
                else:
                    st.warning("No active projects found")
        else:
            try:
                is_inactive = st.session_state.selected_project not in active_project_keys
                
                if is_inactive:
                    st.warning(f"⚠️ This project is currently inactive. Showing historical data only.")
                    
                    latest_metrics = metrics_processor.get_latest_metrics(st.session_state.selected_project)
                    if latest_metrics:
                        tab1, tab2, tab3 = st.tabs(["📊 Last Available Metrics", "📈 Historical Data", "🏷️ Tags"])
                        
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
                                st.markdown("### 📈 Historical Data Analysis")
                                plot_metrics_history(historical_data)
                                display_metric_trends(historical_data)
                                create_download_report(historical_data)
                                
                        with tab3:
                            display_project_tags(st.session_state.selected_project)
                    else:
                        st.info("No historical data available for this inactive project.")
                else:
                    metrics = sonar_api.get_project_metrics(st.session_state.selected_project)
                    if metrics:
                        metrics_dict = {m['metric']: float(m['value']) for m in metrics}
                        MetricsProcessor.store_metrics(st.session_state.selected_project, project_names[st.session_state.selected_project], metrics_dict)

                        tab1, tab2, tab3 = st.tabs(["📊 Executive Dashboard", "📈 Trend Analysis", "🏷️ Tags"])
                        
                        with tab1:
                            display_current_metrics(metrics_dict)
                            
                            st.markdown("### 📋 Historical Overview")
                            historical_data = MetricsProcessor.get_historical_data(st.session_state.selected_project)
                            plot_metrics_history(historical_data)
                        
                        with tab2:
                            if historical_data:
                                display_metric_trends(historical_data)
                                create_download_report(historical_data)
                            else:
                                st.warning("⚠️ No historical data available for trend analysis")
                                
                        with tab3:
                            display_project_tags(st.session_state.selected_project)

            except Exception as e:
                st.error(f"Error displaying project data: {str(e)}")
                reset_project_state()

    except Exception as e:
        st.error(f"Application error: {str(e)}")
        reset_project_state()

if __name__ == "__main__":
    main()