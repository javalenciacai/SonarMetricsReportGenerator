import streamlit as st
import os
from datetime import datetime, timezone, timedelta
import json
from database.schema import execute_query
from services.report_generator import ReportGenerator
from services.scheduler import SchedulerService
import streamlit.components.v1 as components
import html
from main import format_project_name

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
    """Get all configured report schedules with proper name formatting"""
    query = """
    WITH ProjectData AS (
        SELECT 
            r.repo_key,
            r.name,
            r.is_active,
            r.is_marked_for_deletion,
            rs.id,
            rs.report_type,
            rs.frequency,
            rs.next_run_time AT TIME ZONE 'UTC' as next_run_time,
            rs.recipients,
            rs.report_format,
            rs.last_run AT TIME ZONE 'UTC' as last_run,
            rs.is_active as schedule_active
        FROM report_schedules rs
        LEFT JOIN repositories r ON rs.repository_id = r.id
    )
    SELECT * FROM ProjectData
    ORDER BY next_run_time;
    """
    try:
        result = execute_query(query)
        schedules = []
        for row in result:
            schedule_dict = dict(row)
            if schedule_dict.get('name'):
                schedule_dict['formatted_name'] = format_project_name(
                    html.escape(schedule_dict['name']),
                    schedule_dict['is_active'],
                    schedule_dict['is_marked_for_deletion']
                )
            schedules.append(schedule_dict)
        return schedules
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

def render_report_preview(html_content):
    """Render HTML report with proper styling"""
    wrapper_html = f"""
    <div style="
        background-color: #1A1F25;
        border-radius: 12px;
        padding: 2rem;
        margin: 1rem 0;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        font-family: 'SF Pro Display', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    ">
        {html_content}
    </div>
    """
    components.html(wrapper_html, height=800, scrolling=True)

def display_automated_reports():
    """Display the automated reports management interface with modern tech aesthetics"""
    st.markdown("""
        <style>
        /* Global Styles */
        .stApp {
            background-color: #1A1F25;
            color: #A0AEC0;
        }
        
        /* Modern Card Styles */
        .tech-card {
            background: #2D3748;
            border-radius: 12px;
            padding: 25px;
            margin: 20px 0;
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1);
            transition: transform 0.2s ease, box-shadow 0.2s ease;
        }
        .tech-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(0, 0, 0, 0.15);
        }
        
        /* Header Styles */
        .tech-header {
            color: #FAFAFA;
            font-size: 1.5rem;
            font-weight: 600;
            margin-bottom: 1rem;
            padding-bottom: 1rem;
            border-bottom: 2px solid rgba(160, 174, 192, 0.1);
        }
        
        /* Schedule Card Styles */
        .schedule-card {
            background: rgba(45, 55, 72, 0.5);
            border-radius: 10px;
            padding: 20px;
            margin: 15px 0;
            border: 1px solid rgba(160, 174, 192, 0.1);
            transition: all 0.2s ease;
        }
        .schedule-card:hover {
            background: rgba(45, 55, 72, 0.8);
            transform: translateY(-2px);
        }
        
        /* Status Badge Styles */
        .status-badge {
            display: inline-flex;
            align-items: center;
            padding: 6px 12px;
            border-radius: 20px;
            font-size: 0.8rem;
            font-weight: 500;
            transition: all 0.2s ease;
        }
        .status-active {
            background: linear-gradient(135deg, #48BB78 0%, #38A169 100%);
            color: white;
            box-shadow: 0 2px 8px rgba(72, 187, 120, 0.2);
        }
        .status-inactive {
            background: linear-gradient(135deg, #F56565 0%, #C53030 100%);
            color: white;
            box-shadow: 0 2px 8px rgba(245, 101, 101, 0.2);
        }
        
        /* Button Styles */
        .stButton > button {
            background: linear-gradient(135deg, #4A5568 0%, #2D3748 100%) !important;
            color: white !important;
            border: none !important;
            padding: 10px 20px !important;
            border-radius: 8px !important;
            font-weight: 500 !important;
            transition: all 0.2s ease !important;
        }
        .stButton > button:hover {
            transform: translateY(-1px) !important;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15) !important;
        }
        
        /* Form Input Styles */
        .stTextInput > div > div {
            background: #2D3748 !important;
            border: 1px solid rgba(160, 174, 192, 0.1) !important;
            border-radius: 8px !important;
        }
        .stTextArea > div > div {
            background: #2D3748 !important;
            border: 1px solid rgba(160, 174, 192, 0.1) !important;
            border-radius: 8px !important;
        }
        .stSelectbox > div > div {
            background: #2D3748 !important;
            border: 1px solid rgba(160, 174, 192, 0.1) !important;
            border-radius: 8px !important;
        }
        
        /* Tabs Styling */
        .stTabs [data-baseweb="tab-list"] {
            gap: 10px;
            background-color: transparent;
        }
        .stTabs [data-baseweb="tab"] {
            height: 50px;
            background-color: #2D3748;
            border-radius: 8px;
            padding: 0 20px;
            transition: all 0.2s ease;
        }
        .stTabs [data-baseweb="tab"]:hover {
            background-color: #4A5568;
        }
        .stTabs [aria-selected="true"] {
            background-color: #4A5568 !important;
            border-radius: 8px !important;
        }
        </style>
    """, unsafe_allow_html=True)

    st.markdown("""
        <div class="tech-card">
            <h1 class="tech-header">📊 Automated Reports Dashboard</h1>
        </div>
    """, unsafe_allow_html=True)
    
    # Display email configuration status in sidebar
    with st.sidebar:
        display_email_configuration()
    
    # Create tabs with modern styling
    tab1, tab2, tab3 = st.tabs([
        "📅 Schedule Management",
        "👀 Report Preview",
        "⚙️ Configuration"
    ])
    
    with tab1:
        st.markdown("""
            <div class="tech-card">
                <h3 class="tech-header">Create New Report Schedule</h3>
            </div>
        """, unsafe_allow_html=True)
        
        with st.form("new_report_schedule", clear_on_submit=True):
            col1, col2 = st.columns(2)
            
            with col1:
                report_type = st.selectbox(
                    "📋 Report Type",
                    ["Executive Summary", "Full Metrics", "Issues Only"],
                    help="Select the type of report to generate"
                )
                
                frequency = st.selectbox(
                    "⏰ Frequency",
                    ["daily", "weekly", "every_4_hours"],
                    help="How often should this report be generated",
                    format_func=lambda x: x.replace('_', ' ').title()
                )
            
            with col2:
                recipients = st.text_area(
                    "👥 Recipients",
                    help="Enter email addresses, one per line",
                    placeholder="user@example.com\nother@example.com"
                )
                
                report_format = st.selectbox(
                    "📄 Report Format",
                    ["HTML", "PDF", "CSV"],
                    help="Select the format for the report"
                )
            
            submit_button = st.form_submit_button("📅 Create Schedule")
            
            if submit_button:
                with st.spinner("Creating schedule..."):
                    recipient_list = [email.strip() for email in recipients.split('\n') if email.strip()]
                    if not recipient_list:
                        st.error("⚠️ Please enter at least one recipient email address")
                    else:
                        schedule_id = save_report_schedule(
                            report_type, frequency, recipient_list, report_format
                        )
                        if schedule_id:
                            st.success("✅ Report schedule created successfully!")
                            st.rerun()
        
        # Display existing schedules
        schedules = get_report_schedules()
        if schedules:
            st.markdown("""
                <div class="tech-card">
                    <h3 class="tech-header">Active Schedules</h3>
                </div>
            """, unsafe_allow_html=True)
            
            for schedule in schedules:
                with st.expander(
                    f"📄 {schedule['report_type']} ({schedule['frequency'].replace('_', ' ').title()})", 
                    expanded=True
                ):
                    status = "active" if schedule['is_active'] else "inactive"
                    st.markdown(f"""
                        <div class="schedule-card">
                            <span class="status-badge status-{status}">
                                {'🟢 Active' if schedule['is_active'] else '⚫ Inactive'}
                            </span>
                            <p style="margin-top: 10px;">
                                <strong>Format:</strong> {schedule['report_format']} 📄<br>
                                <strong>Recipients:</strong> {', '.join(json.loads(schedule['recipients']) if isinstance(schedule['recipients'], str) else schedule['recipients'])} 👥<br>
                                <strong>Next Run:</strong> {schedule['next_run_time'].strftime('%Y-%m-%d %H:%M UTC')} ⏰<br>
                                {f"<strong>Last Run:</strong> {schedule['last_run'].strftime('%Y-%m-%d %H:%M UTC')} 📅" if schedule['last_run'] else ''}
                            </p>
                        </div>
                    """, unsafe_allow_html=True)
                    
                    col1, col2 = st.columns([1, 1])
                    with col1:
                        new_status = not schedule['is_active']
                        status_label = "🟢 Activate" if new_status else "⚫ Deactivate"
                        if st.button(status_label, key=f"toggle_{schedule['id']}"):
                            with st.spinner(f"{'Activating' if new_status else 'Deactivating'} schedule..."):
                                if toggle_report_schedule(schedule['id'], new_status):
                                    st.success(f"Schedule {status_label.lower()}d successfully!")
                                    st.rerun()
                    
                    with col2:
                        if st.button("🗑️ Delete", key=f"delete_{schedule['id']}", type="secondary"):
                            with st.spinner("Deleting schedule..."):
                                if delete_report_schedule(schedule['id']):
                                    st.success("Schedule deleted successfully!")
                                    st.rerun()
        else:
            st.info("🔍 No report schedules configured yet.")
    
    with tab2:
        st.markdown("""
            <div class="tech-card">
                <h3 class="tech-header">Report Preview</h3>
            </div>
        """, unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        
        with col1:
            preview_type = st.selectbox(
                "Select Report Type 📋",
                ["Daily Report", "Weekly Report", "Metric Change Alert"],
                help="Choose the type of report to preview"
            )
        
        with col2:
            preview_format = st.selectbox(
                "Select Format 📄",
                ["HTML"],
                help="Choose the format for the preview"
            )
        
        if st.button("📋 Generate Preview", type="primary"):
            with st.spinner("Generating preview..."):
                try:
                    report_generator = ReportGenerator()
                    if preview_type == "Daily Report":
                        report = report_generator.generate_daily_report()
                    elif preview_type == "Weekly Report":
                        report = report_generator.generate_weekly_report()
                    else:
                        report = report_generator.check_metric_changes()
                    
                    if report:
                        st.markdown("""
                            <div class="tech-card">
                                <h4 class="tech-header">Preview Output</h4>
                            </div>
                        """, unsafe_allow_html=True)
                        
                        render_report_preview(report)
                    else:
                        st.warning("No data available for preview")
                except Exception as e:
                    st.error(f"Error generating preview: {str(e)}")
    
    with tab3:
        st.markdown("""
            <div class="tech-card">
                <h3 class="tech-header">Configuration Settings</h3>
                <p>Configure email settings and report preferences in your environment variables.</p>
            </div>
        """, unsafe_allow_html=True)