import streamlit as st
from services.sonarcloud import SonarCloudAPI
from services.metrics_processor import MetricsProcessor
from components.metrics_display import display_current_metrics, create_download_report, display_metric_trends
from components.visualizations import plot_metrics_history
from database.schema import initialize_database

def main():
    st.set_page_config(page_title="SonarCloud Metrics Dashboard", layout="wide")
    st.title("SonarCloud Metrics Dashboard")

    # Initialize database
    initialize_database()

    # SonarCloud token input
    token = st.text_input("Enter SonarCloud Token", type="password")
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
