import streamlit as st
from services.sonarcloud import SonarCloudAPI
from services.metrics_processor import MetricsProcessor
from services.scheduler import SchedulerService
from services.report_generator import ReportGenerator
from services.notification_service import NotificationService
from components.metrics_display import display_current_metrics, create_download_report, display_metric_trends, display_multi_project_metrics
from components.visualizations import plot_metrics_history, plot_multi_project_comparison
from database.schema import initialize_database, delete_project_data
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
        # Use fixed width for the logo to ensure proper display
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

def display_project_management(metrics_processor):
    """Display project management section in sidebar"""
    with st.sidebar:
        st.markdown("### 🔧 Project Management")
        
        # Get all projects status
        projects_status = metrics_processor.get_project_status()
        
        if projects_status:
            # Show inactive projects
            inactive_projects = [p for p in projects_status 
                               if p['inactive_duration'] > timedelta(days=30)]
            
            if inactive_projects:
                st.warning(f"⚠️ {len(inactive_projects)} inactive project(s) found")
                
                for project in inactive_projects:
                    with st.expander(f"📁 {project['name']}", expanded=False):
                        st.text(f"Last seen: {project['last_seen'].strftime('%Y-%m-%d')}")
                        st.text(f"Inactive for: {project['inactive_duration'].days} days")
                        
                        if st.button(f"🗑️ Delete {project['name']}", key=f"delete_{project['repo_key']}"):
                            success, message = delete_project_data(project['repo_key'])
                            if success:
                                st.success(f"✅ {message}")
                                st.rerun()
                            else:
                                st.error(f"❌ {message}")
            else:
                st.success("✅ All projects are active")

def main():
    st.set_page_config(
        page_title="SonarCloud Metrics Dashboard",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="expanded"
    )

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
    
    # Display project management section
    display_project_management(metrics_processor)
    
    # Fetch projects
    projects = sonar_api.get_projects()
    if not projects:
        st.warning("No projects found in the organization")
        return

    # Project selection in sidebar with 'All Projects' option
    with sidebar:
        st.markdown("### 🎯 Project Selection")
        project_names = {project['key']: project['name'] for project in projects}
        project_names['all'] = "All Projects"  # Add 'All Projects' option
        selected_project = st.selectbox(
            "Select Project",
            options=['all'] + list(project_names.keys())[:-1],  # Place 'all' at the beginning
            format_func=lambda x: project_names[x]
        )

        st.markdown("---")

        # Automated reporting setup section
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

        if email_recipients and selected_project != 'all':
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
        
        # Fetch metrics for all projects
        all_project_metrics = {}
        for project_key in list(project_names.keys())[:-1]:  # Exclude 'all'
            metrics = sonar_api.get_project_metrics(project_key)
            if metrics:
                metrics_dict = {m['metric']: float(m['value']) for m in metrics}
                all_project_metrics[project_key] = {
                    'name': project_names[project_key],
                    'metrics': metrics_dict
                }
                MetricsProcessor.store_metrics(project_key, project_names[project_key], metrics_dict)

        # Display multi-project metrics
        display_multi_project_metrics(all_project_metrics)
        
        # Plot multi-project comparison
        plot_multi_project_comparison(all_project_metrics)
        
    else:
        # Single project view
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
