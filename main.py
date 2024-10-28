import streamlit as st
from services.sonarcloud import SonarCloudAPI
from services.metrics_processor import MetricsProcessor
from components.metrics_display import display_current_metrics, create_download_report
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

    # Initialize SonarCloud API
    sonar_api = SonarCloudAPI(token)
    
    # Fetch projects
    projects = sonar_api.get_projects()
    if not projects:
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
        metrics_dict = {m['metric']: float(m['value']) for m in metrics}
        MetricsProcessor.store_metrics(selected_project, project_names[selected_project], metrics_dict)

        # Display current metrics
        display_current_metrics(metrics_dict)

        # Display historical data
        st.subheader("Historical Data")
        historical_data = MetricsProcessor.get_historical_data(selected_project)
        plot_metrics_history(historical_data)

        # Download report
        if historical_data:
            create_download_report(historical_data)

if __name__ == "__main__":
    main()
