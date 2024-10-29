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

# Rest of the imports remain the same...

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
        # Existing setup code remains the same...
        
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
                
                # Reset refresh flag
                if force_refresh:
                    st.session_state.refresh_metrics = False
                
                # Rest of the all projects view remains the same...
            
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
                            
                            st.markdown("### 📋 Historical Overview")
                            historical_data = MetricsProcessor.get_historical_data(st.session_state.selected_project)
                            plot_metrics_history(historical_data)
                        
                        with tab2:
                            if historical_data:
                                display_metric_trends(historical_data)
                                create_download_report(historical_data)
                            else:
                                st.warning("⚠️ No historical data available for trend analysis")
                
                # Rest of the inactive project handling remains the same...
                
            except Exception as e:
                st.error(f"Error displaying project data: {str(e)}")
                reset_project_state()
        
        # Rest of the main function remains the same...

    except Exception as e:
        st.error(f"Application error: {str(e)}")
        reset_project_state()

if __name__ == "__main__":
    main()
