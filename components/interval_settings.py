import streamlit as st
from database.schema import store_update_preferences, get_update_preferences
from services.scheduler import SchedulerService

def get_interval_options():
    """Get available update interval options"""
    return {
        '5 minutes': 300,
        '15 minutes': 900,
        '30 minutes': 1800,
        '1 hour': 3600,
        '2 hours': 7200,
        '4 hours': 14400,
        '8 hours': 28800,
        '12 hours': 43200,
        '24 hours': 86400
    }

def display_interval_settings(entity_type, entity_id, scheduler_service):
    """Display and manage update interval settings"""
    st.markdown("### ⏱️ Update Interval Settings")
    
    # Get current preferences
    current_prefs = get_update_preferences(entity_type, entity_id)
    current_interval = current_prefs['update_interval']
    last_update = current_prefs['last_update']
    
    # Create interval options
    interval_options = get_interval_options()
    current_option = next(
        (k for k, v in interval_options.items() if v == current_interval),
        '1 hour'
    )
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        new_interval = st.selectbox(
            "Select Update Interval",
            options=list(interval_options.keys()),
            index=list(interval_options.keys()).index(current_option),
            help="Choose how often metrics should be updated"
        )
    
    with col2:
        if st.button("Apply", help="Save and apply the new update interval"):
            interval_seconds = interval_options[new_interval]
            if store_update_preferences(entity_type, entity_id, interval_seconds):
                scheduler_service.schedule_metrics_update(
                    update_entity_metrics,  # This function needs to be implemented in the main app
                    entity_type,
                    entity_id,
                    interval_seconds
                )
                st.success("✅ Update interval changed successfully")
            else:
                st.error("Failed to update interval settings")
    
    if last_update:
        st.info(f"🕒 Last updated: {last_update}")
    
    st.markdown("""
        <small style='color: #A0AEC0;'>
        Note: More frequent updates may impact performance. Choose an interval that balances 
        your needs with system resources.
        </small>
    """, unsafe_allow_html=True)
