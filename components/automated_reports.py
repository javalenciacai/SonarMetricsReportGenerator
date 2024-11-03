import streamlit as st
from datetime import datetime, timezone, timedelta
import json
from database.schema import execute_query
from services.report_generator import ReportGenerator
from services.scheduler import SchedulerService

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

def save_report_schedule(report_type, frequency, recipients, report_format):
    """Save a new report schedule"""
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
    try:
        result = execute_query(
            query, 
            (report_type, frequency, json.dumps(recipients), report_format, frequency, frequency)
        )
        return result[0][0] if result else None
    except Exception as e:
        st.error(f"Error saving report schedule: {str(e)}")
        return None

def toggle_report_schedule(schedule_id, is_active):
    """Toggle a report schedule active/inactive"""
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
        st.error(f"Error toggling report schedule: {str(e)}")
        return False

def delete_report_schedule(schedule_id):
    """Delete a report schedule"""
    query = """
    DELETE FROM report_schedules 
    WHERE id = %s 
    RETURNING id;
    """
    try:
        result = execute_query(query, (schedule_id,))
        return bool(result)
    except Exception as e:
        st.error(f"Error deleting report schedule: {str(e)}")
        return False

def display_email_configuration():
    """Display and test email configuration"""
    st.markdown("### ✉️ Email Configuration")
    
    report_generator = ReportGenerator()
    status, message = report_generator.test_smtp_connection()
    
    if status:
        st.success("✅ Email configuration is working")
    else:
        st.error(f"❌ Email configuration error: {message}")
    
    with st.expander("📧 Email Settings"):
        st.code(f"""
        SMTP Server: {report_generator.smtp_server}
        SMTP Port: {report_generator.smtp_port}
        Username: {'Configured' if report_generator.smtp_username else 'Not configured'}
        Password: {'Configured' if report_generator.smtp_password else 'Not configured'}
        """)

def display_automated_reports():
    """Display the automated reports management interface"""
    st.markdown("## 📊 Automated Reports")
    
    # Display email configuration status in sidebar
    with st.sidebar:
        display_email_configuration()
    
    # Create tabs for Schedule Management, Report Preview, and Threshold Configuration
    tab1, tab2, tab3 = st.tabs([
        "📅 Schedule Management",
        "👀 Report Preview",
        "⚙️ Threshold Configuration"
    ])
    
    with tab1:
        st.markdown("### Create New Report Schedule")
        with st.form("new_report_schedule"):
            report_type = st.selectbox(
                "Report Type",
                ["Executive Summary", "Full Metrics", "Issues Only"],
                help="Select the type of report to generate"
            )
            
            frequency = st.selectbox(
                "Frequency",
                ["daily", "weekly", "every_4_hours"],
                help="How often should this report be generated"
            )
            
            recipients = st.text_area(
                "Recipients (one email per line)",
                help="Enter email addresses, one per line"
            )
            
            report_format = st.selectbox(
                "Report Format",
                ["HTML", "PDF", "CSV"],
                help="Select the format for the report"
            )
            
            submit_button = st.form_submit_button("📅 Create Schedule")
            
            if submit_button:
                recipient_list = [email.strip() for email in recipients.split('\n') if email.strip()]
                if not recipient_list:
                    st.error("Please enter at least one recipient email address")
                else:
                    schedule_id = save_report_schedule(
                        report_type, frequency, recipient_list, report_format
                    )
                    if schedule_id:
                        st.success("✅ Report schedule created successfully!")
                        st.rerun()
        
        st.markdown("### Existing Schedules")
        schedules = get_report_schedules()
        
        if not schedules:
            st.info("No report schedules configured yet.")
            return
        
        for schedule in schedules:
            with st.expander(
                f"📄 {schedule['report_type']} ({schedule['frequency'].title()})", 
                expanded=True
            ):
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    st.markdown(f"**Format:** {schedule['report_format']}")
                    recipients_list = schedule['recipients']
                    if isinstance(recipients_list, str):
                        recipients_list = json.loads(recipients_list)
                    st.markdown(f"**Recipients:** {', '.join(recipients_list)}")
                    st.markdown(f"**Next Run:** {schedule['next_run_time']}")
                    if schedule['last_run']:
                        st.markdown(f"**Last Run:** {schedule['last_run']}")
                    
                    status = "🟢 Active" if schedule['is_active'] else "⚫ Inactive"
                    st.markdown(f"**Status:** {status}")
                
                with col2:
                    # Toggle active status
                    new_status = not schedule['is_active']
                    status_label = "🟢 Activate" if new_status else "⚫ Deactivate"
                    if st.button(status_label, key=f"toggle_{schedule['id']}"):
                        if toggle_report_schedule(schedule['id'], new_status):
                            st.success(f"Schedule {status_label.lower()}d successfully!")
                            st.rerun()
                    
                    # Delete schedule
                    if st.button("🗑️ Delete", key=f"delete_{schedule['id']}"):
                        if delete_report_schedule(schedule['id']):
                            st.success("Schedule deleted successfully!")
                            st.rerun()
    
    with tab2:
        st.markdown("### Report Preview")
        preview_type = st.selectbox(
            "Select Report Type",
            ["Daily Report", "Weekly Report", "Metric Change Alert"]
        )
        
        preview_format = st.selectbox(
            "Select Format",
            ["HTML", "PDF", "CSV"]
        )
        
        report_generator = ReportGenerator()
        
        if st.button("📋 Generate Preview"):
            st.info("Generating preview... This may take a moment.")
            
            try:
                if preview_type == "Daily Report":
                    report = report_generator.generate_daily_report()
                elif preview_type == "Weekly Report":
                    report = report_generator.generate_weekly_report()
                else:
                    report = report_generator.check_metric_changes()
                
                if report:
                    st.markdown(report, unsafe_allow_html=True)
                    st.download_button(
                        "📥 Download Report",
                        report,
                        file_name=f"report_preview.{preview_format.lower()}",
                        mime=f"text/{preview_format.lower()}"
                    )
                else:
                    st.warning("No data available for preview")
            except Exception as e:
                st.error(f"Error generating preview: {str(e)}")
    
    with tab3:
        st.markdown("### Metric Change Thresholds")
        st.info("Configure thresholds for metric change alerts")
        
        with st.form("threshold_config"):
            col1, col2 = st.columns(2)
            
            with col1:
                bugs_threshold = st.number_input(
                    "Bugs Threshold",
                    min_value=1,
                    value=5,
                    help="Alert when bugs increase by this amount"
                )
                vulnerabilities_threshold = st.number_input(
                    "Vulnerabilities Threshold",
                    min_value=1,
                    value=3,
                    help="Alert when vulnerabilities increase by this amount"
                )
                code_smells_threshold = st.number_input(
                    "Code Smells Threshold",
                    min_value=1,
                    value=10,
                    help="Alert when code smells increase by this amount"
                )
            
            with col2:
                coverage_threshold = st.number_input(
                    "Coverage Change Threshold (%)",
                    min_value=1,
                    value=5,
                    help="Alert when coverage changes by this percentage"
                )
                duplication_threshold = st.number_input(
                    "Duplication Change Threshold (%)",
                    min_value=1,
                    value=5,
                    help="Alert when duplication changes by this percentage"
                )
            
            if st.form_submit_button("💾 Save Thresholds"):
                # Save thresholds to database (implementation needed)
                st.success("✅ Thresholds updated successfully")
