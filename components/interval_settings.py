import streamlit as st
from database.schema import store_update_preferences, get_update_preferences
import logging
from services.metrics_updater import update_entity_metrics

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
                    # Schedule metrics update with proper error handling
                    try:
                        scheduler_service.schedule_metrics_update(
                            update_entity_metrics,
                            entity_type,
                            entity_id,
                            interval_seconds
                        )
                        st.success("✅ Update interval changed successfully")
                        logger.info(f"Update interval changed for {entity_type} {entity_id} to {interval_seconds} seconds")
                    except Exception as e:
                        logger.error(f"Failed to schedule metrics update: {str(e)}")
                        st.error(f"❌ Failed to schedule update: {str(e)}")
                else:
                    error_msg = "Project not found" if entity_type == 'repository' else "Group not found"
                    logger.error(f"Failed to update interval settings: {error_msg}")
                    st.error(f"❌ Failed to update interval settings: {error_msg}")
            except ValueError as e:
                logger.error(f"Invalid input: {str(e)}")
                st.error(f"❌ Invalid input: {str(e)}")
            except Exception as e:
                logger.error(f"Error updating settings: {str(e)}")
                st.error(f"❌ Error updating settings: {str(e)}")
    
    if last_update:
        st.info(f"🕒 Last updated: {last_update}")
    
    st.markdown("""
        <small style='color: #A0AEC0;'>
        Note: More frequent updates may impact performance. Choose an interval that balances 
        your needs with system resources.
        </small>
    """, unsafe_allow_html=True)
