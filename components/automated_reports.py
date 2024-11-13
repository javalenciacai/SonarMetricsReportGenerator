import streamlit as st
import os
from datetime import datetime, timezone, timedelta
import json
from database.schema import execute_query
from services.report_generator import ReportGenerator
from services.scheduler import SchedulerService
import streamlit.components.v1 as components

def display_email_configuration():
    """Display email configuration status"""
    st.markdown("### ✉️ Email Configuration")
    
    smtp_server = os.getenv('SMTP_SERVER')
    smtp_port = os.getenv('SMTP_PORT')
    smtp_username = os.getenv('SMTP_USERNAME')
    smtp_password = os.getenv('SMTP_PASSWORD')
    
    if all([smtp_server, smtp_port, smtp_username, smtp_password]):
        try:
            report_generator = ReportGenerator()
            success, message = report_generator.test_smtp_connection()
            if success:
                st.markdown("✅ Email Configuration: Connected")
            else:
                st.markdown("❌ Email Configuration: Error")
                st.error(f"Connection failed: {message}")
        except Exception as e:
            st.markdown("❌ Email Configuration: Error")
            st.error(f"Configuration error: {str(e)}")
    else:
        st.markdown("⚠️ Email Configuration: Not configured")
        st.warning("Please set up SMTP configuration in environment variables")

def get_report_schedules():
    """Get all configured report schedules"""
    query = """
    SELECT 
        id,
        report_type,
        frequency,
        next_run_time AT TIME ZONE 'UTC' as next_run_time,
        recipients,
        report_format,
        last_run AT TIME ZONE 'UTC' as last_run,
        is_active
    FROM report_schedules
    ORDER BY next_run_time;
    """
    try:
        result = execute_query(query)
        return [dict(row) for row in result] if result else []
    except Exception as e:
        st.error(f"Error fetching report schedules: {str(e)}")
        return []

def check_existing_schedule(report_type, frequency, recipients, report_format):
    """Check if a schedule with the same configuration already exists"""
    query = """
    SELECT id FROM report_schedules 
    WHERE report_type = %s 
    AND frequency = %s 
    AND recipients = %s 
    AND report_format = %s;
    """
    try:
        result = execute_query(query, (report_type, frequency, json.dumps(recipients), report_format))
        return bool(result)
    except Exception as e:
        st.error(f"Error checking existing schedule: {str(e)}")
        return False

def save_report_schedule(report_type, frequency, recipients, report_format):
    """Save a new report schedule with duplicate checking"""
    try:
        # Check for existing schedule with same configuration
        if check_existing_schedule(report_type, frequency, recipients, report_format):
            st.warning("A schedule with identical configuration already exists.")
            return None

        query = """
        INSERT INTO report_schedules (
            report_type, frequency, recipients, 
            report_format, is_active, next_run_time
        ) VALUES (
            %s, %s, %s, %s, true, 
            CASE 
                WHEN %s = 'daily' THEN CURRENT_DATE + INTERVAL '1 day' + INTERVAL '1 hour'
                WHEN %s = 'weekly' THEN date_trunc('week', CURRENT_DATE) + INTERVAL '1 week' + INTERVAL '2 hours'
                ELSE CURRENT_TIMESTAMP + INTERVAL '1 hour'
            END
        ) RETURNING id;
        """
        result = execute_query(
            query, 
            (report_type, frequency, json.dumps(recipients), report_format, frequency, frequency)
        )
        return result[0][0] if result else None
    except Exception as e:
        st.error(f"Error saving report schedule: {str(e)}")
        return None

def delete_report_schedule(schedule_id):
    """Delete a report schedule"""
    query = "DELETE FROM report_schedules WHERE id = %s RETURNING id;"
    try:
        result = execute_query(query, (schedule_id,))
        return bool(result)
    except Exception as e:
        st.error(f"Error deleting report schedule: {str(e)}")
        return False

def toggle_schedule_status(schedule_id, is_active):
    """Toggle the active status of a report schedule"""
    query = """
    UPDATE report_schedules 
    SET is_active = %s 
    WHERE id = %s 
    RETURNING id;
    """
    try:
        result = execute_query(query, (is_active, schedule_id))
        return bool(result)
    except Exception as e:
        st.error(f"Error updating schedule status: {str(e)}")
        return False

def display_automated_reports():
    """Display automated reports configuration interface"""
    st.title("🤖 Automated Reports")
    
    # Display email configuration status
    display_email_configuration()
    
    # Create new report schedule
    st.markdown("### 📅 Create New Schedule")
    
    with st.form(key="new_schedule_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            report_type = st.selectbox(
                "Report Type",
                ["daily", "weekly", "alerts"],
                help="Select the type of report to generate"
            )
            
            frequency = st.selectbox(
                "Frequency",
                ["daily", "weekly"] if report_type != "alerts" else ["4-hourly"],
                help="Select how often the report should be generated"
            )
        
        with col2:
            recipients = st.text_input(
                "Recipients (comma-separated emails)",
                help="Enter email addresses separated by commas"
            )
            
            report_format = st.selectbox(
                "Report Format",
                ["HTML", "Plain Text"],
                help="Select the format for the report"
            )
            
        submit_schedule = st.form_submit_button("Create Schedule")
        
        if submit_schedule:
            if not recipients:
                st.error("Please enter at least one recipient email address")
            else:
                recipient_list = [email.strip() for email in recipients.split(",")]
                schedule_id = save_report_schedule(
                    report_type, 
                    frequency, 
                    recipient_list,
                    report_format
                )
                
                if schedule_id:
                    st.success("✅ Report schedule created successfully!")
                    if not st.session_state.get('pending_rerun'):
                        st.session_state.pending_rerun = True
                        st.rerun()
    
    # Display existing schedules
    st.markdown("### 📋 Existing Schedules")
    schedules = get_report_schedules()
    
    if not schedules:
        st.info("No report schedules configured yet")
    else:
        for schedule in schedules:
            with st.expander(
                f"{schedule['report_type'].title()} Report - {schedule['frequency']} "
                f"({'Active' if schedule['is_active'] else 'Inactive'})"
            ):
                col1, col2, col3 = st.columns([2, 2, 1])
                
                with col1:
                    st.markdown(f"**Recipients:** {', '.join(schedule['recipients'])}")
                    st.markdown(f"**Format:** {schedule['report_format']}")
                
                with col2:
                    next_run = schedule['next_run_time'].strftime('%Y-%m-%d %H:%M UTC') if schedule['next_run_time'] else 'Not scheduled'
                    last_run = schedule['last_run'].strftime('%Y-%m-%d %H:%M UTC') if schedule['last_run'] else 'Never'
                    
                    st.markdown(f"**Next Run:** {next_run}")
                    st.markdown(f"**Last Run:** {last_run}")
                
                with col3:
                    status = schedule['is_active']
                    if st.toggle("Active", value=status, key=f"toggle_{schedule['id']}"):
                        if not status:
                            if toggle_schedule_status(schedule['id'], True):
                                st.success("Schedule activated")
                                if not st.session_state.get('pending_rerun'):
                                    st.session_state.pending_rerun = True
                                    st.rerun()
                    else:
                        if status:
                            if toggle_schedule_status(schedule['id'], False):
                                st.warning("Schedule deactivated")
                                if not st.session_state.get('pending_rerun'):
                                    st.session_state.pending_rerun = True
                                    st.rerun()
                    
                    if st.button("🗑️", key=f"delete_{schedule['id']}"):
                        if delete_report_schedule(schedule['id']):
                            st.success("Schedule deleted")
                            if not st.session_state.get('pending_rerun'):
                                st.session_state.pending_rerun = True
                                st.rerun()
