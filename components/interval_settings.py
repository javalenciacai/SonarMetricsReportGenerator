import streamlit as st
from database.schema import store_update_preferences, get_update_preferences
from services.metrics_updater import update_entity_metrics
from datetime import datetime, timezone

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

def format_timestamp_utc(timestamp):
    """Format timestamp in UTC"""
    if timestamp:
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        return timestamp.strftime("%Y-%m-%d %H:%M:%S UTC")
    return None

def display_interval_settings(entity_type, entity_id, scheduler_service):
    """Display and manage update interval settings"""
    if not entity_id:
        st.warning("⚠️ Please select a project or group first")
        return

    st.markdown("### ⏱️ Update Interval Settings")
    
    # Get current preferences
    current_prefs = get_update_preferences(entity_type, entity_id)
    current_interval = current_prefs.get('update_interval', 3600)
    last_update = current_prefs.get('last_update')
    
    # Create interval options
    interval_options = get_interval_options()
    current_option = next(
        (k for k, v in interval_options.items() if v == current_interval),
        '1 hour'
    )

    # Use form to batch updates
    with st.form(key=f"interval_settings_{entity_type}_{entity_id}"):
        new_interval = st.selectbox(
            "Select Update Interval",
            options=list(interval_options.keys()),
            index=list(interval_options.keys()).index(current_option),
            help="Choose how often metrics should be updated",
            key=f"interval_select_{entity_id}"
        )
        
        submit_button = st.form_submit_button(
            "Apply Changes",
            help="Save and apply the new update interval"
        )
        
        if submit_button:
            try:
                interval_seconds = interval_options[new_interval]
                
                # Store preferences using the entity_id directly
                if store_update_preferences(entity_type, entity_id, interval_seconds):
                    scheduler_service.schedule_metrics_update(
                        update_entity_metrics,
                        entity_type,
                        entity_id,
                        interval_seconds
                    )
                    st.success("✅ Update interval changed successfully")
                else:
                    if entity_type == 'repository':
                        st.error("❌ Failed to update interval settings: Project not found")
                    else:
                        st.error("❌ Failed to update interval settings: Group not found")
            except ValueError as e:
                st.error(f"❌ Invalid input: {str(e)}")
            except Exception as e:
                st.error(f"❌ Error updating settings: {str(e)}")
    
    if last_update:
        formatted_update = format_timestamp_utc(last_update)
        st.info(f"🕒 Last updated: {formatted_update}")
    
    st.markdown("""
        <small style='color: #A0AEC0;'>
        Note: More frequent updates may impact performance. Choose an interval that balances 
        your needs with system resources.
        </small>
    """, unsafe_allow_html=True)
