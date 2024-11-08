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

[... rest of the file remains unchanged ...]
