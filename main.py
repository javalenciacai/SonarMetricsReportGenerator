import streamlit as st
from services.sonarcloud import SonarCloudAPI
from services.metrics_processor import MetricsProcessor
from services.scheduler import SchedulerService
from services.report_generator import ReportGenerator
from services.notification_service import NotificationService
from components.metrics_display import display_current_metrics, create_download_report, display_metric_trends, display_multi_project_metrics
from components.visualizations import plot_metrics_history, plot_multi_project_comparison
from database.schema import initialize_database
import os
from datetime import datetime, timedelta

# Initialize scheduler as a global variable
scheduler = SchedulerService()
report_generator = None
notification_service = None

def setup_automated_reports(sonar_api, project_key, email_recipients):
    """Setup automated report generation"""
    global report_generator
    if not report_generator:
        return False
    
    try:
        def generate_daily_report():
            report_data, message = report_generator.generate_project_report(project_key, 'daily')
            if report_data:
                success, send_message = report_generator.send_report_email(report_data, email_recipients)
                if not success:
                    st.error(f"Failed to send daily report: {send_message}")

        def generate_weekly_report():
            report_data, message = report_generator.generate_project_report(project_key, 'weekly')
            if report_data:
                success, send_message = report_generator.send_report_email(report_data, email_recipients)
                if not success:
                    st.error(f"Failed to send weekly report: {send_message}")

        def check_metric_changes():
            """Check for significant metric changes"""
            metrics = sonar_api.get_project_metrics(project_key)
            if metrics:
                metrics_dict = {m['metric']: float(m['value']) for m in metrics}
                historical_data = MetricsProcessor.get_historical_data(project_key)
                
                if historical_data:
                    notification_service.send_notification(
                        project_key=project_key,
                        metrics_data=metrics_dict,
                        historical_data=historical_data,
                        recipients=email_recipients
                    )

        scheduler.schedule_daily_report(generate_daily_report, hour=1, minute=0)
        scheduler.schedule_weekly_report(generate_weekly_report, day_of_week=0, hour=2, minute=0)
        scheduler.schedule_metric_checks(check_metric_changes, interval_hours=4)
        
        return True
    except Exception as e:
        st.error(f"Error setting up automated reports: {str(e)}")
        return False

def setup_sidebar():
    """Configure and display sidebar content"""
    with st.sidebar:
        st.markdown("""
            <div style="display: flex; justify-content: center; margin-bottom: 1rem;">
                <img src="static/sonarcloud-logo.svg" alt="SonarCloud Logo" style="width: 180px; height: auto;">
            </div>
        """, unsafe_allow_html=True)
        st.markdown("---")
        
        st.markdown("""
            <style>
            .sidebar-info {
                padding: 1rem;
                background-color: #1A1F25;
                border-radius: 0.5rem;
                margin-bottom: 1rem;
            }
            </style>
        """, unsafe_allow_html=True)
        
        return st.sidebar

def display_project_management(metrics_processor, active_project_keys):
    """Display project management section in sidebar"""
    with st.sidebar:
        st.markdown("### 🔧 Project Management")
        
        # Get all projects status
        projects_status = metrics_processor.get_project_status()
        
        if projects_status:
            # Update inactive status for projects not in active_project_keys
            if active_project_keys:
                metrics_processor.check_and_mark_inactive_projects(active_project_keys)
            
            # Show inactive projects
            inactive_projects = [p for p in projects_status if not p['is_active']]
            active_projects = [p for p in projects_status if p['is_active']]
            
            # Display active projects count
            st.success(f"✅ {len(active_projects)} active project(s)")
            
            # Display inactive projects
            if inactive_projects:
                st.warning(f"⚠️ {len(inactive_projects)} inactive project(s)")
                
                for project in inactive_projects:
                    with st.expander(f"📁 {project['name']} (Inactive)", expanded=False):
                        st.text(f"Last seen: {project['last_seen'].strftime('%Y-%m-%d')}")
                        st.text(f"Inactive for: {project['inactive_duration'].days} days")
                        st.markdown("ℹ️ *This project is no longer found in SonarCloud*")
                        
                        if project.get('is_marked_for_deletion'):
                            st.info("🗑️ Marked for deletion")
                        
                        # Show historical data access button
                        if st.button(f"📊 View Historical Data", key=f"hist_{project['repo_key']}"):
                            st.session_state.selected_project = project['repo_key']
                            st.session_state.show_inactive = True
            else:
                st.success("✅ No inactive projects")

def main():
    st.set_page_config(
        page_title="SonarCloud Metrics Dashboard",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    # Initialize session state for project selection
    if 'selected_project' not in st.session_state:
        st.session_state.selected_project = None
    if 'show_inactive' not in st.session_state:
        st.session_state.show_inactive = False

    # Initialize database
    initialize_database()
    
    # Initialize global variables
    global report_generator, notification_service

    # Start the scheduler
    if not scheduler.scheduler.running:
        scheduler.start()

    # Setup sidebar
    sidebar = setup_sidebar()
    
    # SonarCloud token input
    token = os.getenv('SONARCLOUD_TOKEN') or st.text_input("Enter SonarCloud Token", type="password")
    if not token:
        st.warning("⚠️ Please enter your SonarCloud token to continue")
        return

    # Initialize SonarCloud API and validate token
    sonar_api = SonarCloudAPI(token)
    is_valid, message = sonar_api.validate_token()
    
    if not is_valid:
        st.error(message)
        return
    
    # Initialize report generator and notification service after validating token
    report_generator = ReportGenerator(sonar_api)
    notification_service = NotificationService(report_generator)
    metrics_processor = MetricsProcessor()
    
    st.success(f"✅ Token validated successfully. Using organization: {sonar_api.organization}")
    
    # Fetch active projects from SonarCloud
    active_projects = sonar_api.get_projects()
    if not active_projects:
        st.warning("No active projects found in the organization")
    
    # Get list of active project keys
    active_project_keys = [project['key'] for project in active_projects] if active_projects else []
    
    # Get all projects including inactive ones
    all_projects_status = metrics_processor.get_project_status()
    
    # Create project names dictionary including both active and inactive projects
    project_names = {}
    if active_projects:
        for project in active_projects:
            project_names[project['key']] = f"✅ {project['name']}"
    
    # Add inactive projects to the dictionary
    for project in all_projects_status:
        if not project['is_active']:
            project_names[project['repo_key']] = f"⚠️ {project['name']} (Inactive)"
    
    # Add "All Projects" option
    project_names['all'] = "📊 All Projects"
    
    # Display project management section
    display_project_management(metrics_processor, active_project_keys)
    
    # Project selection in sidebar
    with sidebar:
        st.markdown("### 🎯 Project Selection")
        
        # Use session state for project selection if set from inactive project view
        if st.session_state.selected_project and st.session_state.selected_project in project_names:
            selected_project = st.session_state.selected_project
        else:
            selected_project = st.selectbox(
                "Select Project",
                options=['all'] + list(project_names.keys())[:-1],
                format_func=lambda x: project_names[x]
            )
            st.session_state.selected_project = selected_project

        st.markdown("---")

        # Automated reporting setup section (only for active projects)
        if selected_project != 'all' and selected_project in active_project_keys:
            st.markdown("### ⚙️ Automation Setup")
            
            # Email configuration status
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
                        report_data, gen_message = report_generator.generate_project_report(selected_project, 'daily')
                        if report_data:
                            success, send_message = report_generator.send_report_email(report_data, recipients_list)
                            if success:
                                if setup_automated_reports(sonar_api, selected_project, recipients_list):
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

    if selected_project == 'all':
        st.markdown("## 📊 Multi-Project Overview")
        
        # Fetch metrics for active projects
        all_project_metrics = {}
        for project_key in active_project_keys:
            metrics = sonar_api.get_project_metrics(project_key)
            if metrics:
                metrics_dict = {m['metric']: float(m['value']) for m in metrics}
                all_project_metrics[project_key] = {
                    'name': project_names[project_key].replace('✅ ', ''),  # Remove status emoji
                    'metrics': metrics_dict
                }
                MetricsProcessor.store_metrics(project_key, project_names[project_key], metrics_dict)

        # Display multi-project metrics
        display_multi_project_metrics(all_project_metrics)
        
        # Plot multi-project comparison
        plot_multi_project_comparison(all_project_metrics)
        
    else:
        # Check if selected project is inactive
        is_inactive = selected_project not in active_project_keys
        
        if is_inactive:
            st.warning(f"⚠️ This project is currently inactive. Showing historical data only.")
            
            # Display historical data for inactive project
            historical_data = MetricsProcessor.get_historical_data(selected_project)
            if historical_data:
                st.markdown("### 📈 Historical Data Analysis")
                plot_metrics_history(historical_data)
                display_metric_trends(historical_data)
                create_download_report(historical_data)
            else:
                st.info("No historical data available for this inactive project.")
        else:
            # Regular active project view
            metrics = sonar_api.get_project_metrics(selected_project)
            if metrics:
                metrics_dict = {m['metric']: float(m['value']) for m in metrics}
                MetricsProcessor.store_metrics(selected_project, project_names[selected_project], metrics_dict)

                # Create tabs for different views
                tab1, tab2 = st.tabs(["📊 Executive Dashboard", "📈 Trend Analysis"])
                
                with tab1:
                    display_current_metrics(metrics_dict)
                    
                    st.markdown("### 📋 Historical Overview")
                    historical_data = MetricsProcessor.get_historical_data(selected_project)
                    plot_metrics_history(historical_data)
                
                with tab2:
                    if historical_data:
                        display_metric_trends(historical_data)
                        create_download_report(historical_data)
                    else:
                        st.warning("⚠️ No historical data available for trend analysis")

if __name__ == "__main__":
    main()
