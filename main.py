import streamlit as st
from services.sonarcloud import SonarCloudAPI
from services.metrics_processor import MetricsProcessor
from services.scheduler import SchedulerService
from services.report_generator import ReportGenerator
from services.notification_service import NotificationService
from components.metrics_display import display_current_metrics, create_download_report, display_metric_trends
from components.visualizations import plot_metrics_history
from database.schema import initialize_database
import os

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
        st.image("https://www.sonarqube.org/logos/index/sonarcloud-logo.png", width=200)
        st.markdown("---")
        
        st.markdown("""
            <style>
            .sidebar-info {
                padding: 1rem;
                background-color: #f8f9fa;
                border-radius: 0.5rem;
                margin-bottom: 1rem;
            }
            </style>
        """, unsafe_allow_html=True)
        
        return st.sidebar

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
    
    st.success(f"✅ Token validated successfully. Using organization: {sonar_api.organization}")
    
    # Fetch projects
    projects = sonar_api.get_projects()
    if not projects:
        st.warning("No projects found in the organization")
        return

    # Project selection in sidebar
    with sidebar:
        st.markdown("### 🎯 Project Selection")
        project_names = {project['key']: project['name'] for project in projects}
        selected_project = st.selectbox(
            "Select Project",
            options=list(project_names.keys()),
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

    if selected_project:
        # Fetch and store metrics
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
