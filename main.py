import streamlit as st
from services.sonarcloud import SonarCloudAPI
from services.metrics_processor import MetricsProcessor
from services.scheduler import SchedulerService
from services.report_generator import ReportGenerator
from components.metrics_display import display_current_metrics, create_download_report, display_metric_trends
from components.visualizations import plot_metrics_history
from database.schema import initialize_database
import os

# Initialize scheduler as a global variable
scheduler = SchedulerService()
report_generator = None

def setup_automated_reports(sonar_api, project_key, email_recipients):
    """Setup automated report generation"""
    global report_generator
    if report_generator is None:
        report_generator = ReportGenerator(sonar_api)

    def generate_daily_report():
        report_data = report_generator.generate_project_report(project_key, 'daily')
        if report_data:
            report_generator.send_report_email(report_data, email_recipients)

    def generate_weekly_report():
        report_data = report_generator.generate_project_report(project_key, 'weekly')
        if report_data:
            report_generator.send_report_email(report_data, email_recipients)

    # Schedule daily report at 1 AM
    scheduler.schedule_daily_report(generate_daily_report, hour=1, minute=0)
    
    # Schedule weekly report for Monday at 2 AM
    scheduler.schedule_weekly_report(generate_weekly_report, day_of_week=0, hour=2, minute=0)

def main():
    st.set_page_config(page_title="SonarCloud Metrics Dashboard", layout="wide")
    st.title("SonarCloud Metrics Dashboard")

    # Initialize database
    initialize_database()

    # Start the scheduler
    if not scheduler.scheduler.running:
        scheduler.start()

    # SonarCloud token input
    token = os.getenv('SONARCLOUD_TOKEN') or st.text_input("Enter SonarCloud Token", type="password")
    if not token:
        st.warning("Please enter your SonarCloud token to continue")
        return

    # Initialize SonarCloud API and validate token
    sonar_api = SonarCloudAPI(token)
    is_valid, message = sonar_api.validate_token()
    
    if not is_valid:
        st.error(message)
        return
    
    st.success(f"Token validated successfully. Using organization: {sonar_api.organization}")
    
    # Fetch projects
    projects = sonar_api.get_projects()
    if not projects:
        st.warning("No projects found in the organization")
        return

    # Project selection
    project_names = {project['key']: project['name'] for project in projects}
    selected_project = st.selectbox(
        "Select Project",
        options=list(project_names.keys()),
        format_func=lambda x: project_names[x]
    )

    if selected_project:
        # Automated reporting setup section
        st.sidebar.subheader("Automated Reports")
        email_recipients = st.sidebar.text_input(
            "Email Recipients (comma-separated)",
            help="Enter email addresses to receive automated reports"
        )

        if email_recipients:
            if st.sidebar.button("Setup Automated Reports"):
                recipients_list = [email.strip() for email in email_recipients.split(",")]
                setup_automated_reports(sonar_api, selected_project, recipients_list)
                st.sidebar.success("Automated reports scheduled successfully!")

        # Fetch and store metrics
        metrics = sonar_api.get_project_metrics(selected_project)
        if metrics:
            metrics_dict = {m['metric']: float(m['value']) for m in metrics}
            MetricsProcessor.store_metrics(selected_project, project_names[selected_project], metrics_dict)

            # Create tabs for different views
            tab1, tab2 = st.tabs(["Current Status", "Trend Analysis"])
            
            with tab1:
                # Display current metrics with status indicators
                display_current_metrics(metrics_dict)
                
                # Display historical data visualization
                st.subheader("Historical Data")
                historical_data = MetricsProcessor.get_historical_data(selected_project)
                plot_metrics_history(historical_data)
            
            with tab2:
                # Display metric trends and comparisons
                if historical_data:
                    display_metric_trends(historical_data)
                    create_download_report(historical_data)
                else:
                    st.warning("No historical data available for trend analysis")

if __name__ == "__main__":
    main()
