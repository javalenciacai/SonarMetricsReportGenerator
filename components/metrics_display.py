import streamlit as st
import pandas as pd
from services.metric_analyzer import MetricAnalyzer
from utils.helpers import format_code_lines, format_technical_debt
from database.schema import get_update_preferences
from database.connection import execute_query
from datetime import datetime, timezone
from services.metrics_processor import MetricsProcessor

def format_update_interval(seconds):
    """Format update interval in a human-readable way"""
    if seconds >= 86400:
        return f"{seconds//86400}d"
    elif seconds >= 3600:
        return f"{seconds//3600}h"
    elif seconds >= 60:
        return f"{seconds//60}m"
    return f"{seconds}s"

def format_last_update(timestamp):
    """Format last update timestamp in a human-readable way"""
    if not timestamp:
        return "No updates yet"
    
    try:
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        if not timestamp.tzinfo:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        
        now = datetime.now(timezone.utc)
        diff = now - timestamp
        
        if diff.days > 0:
            return f"{diff.days}d ago"
        elif diff.seconds >= 3600:
            return f"{diff.seconds//3600}h ago"
        elif diff.seconds >= 60:
            return f"{diff.seconds//60}m ago"
        return f"{diff.seconds}s ago"
    except (ValueError, TypeError) as e:
        print(f"Error formatting timestamp: {str(e)}")
        return "Invalid timestamp"

def get_last_update_timestamp(project_key):
    """Get the latest timestamp from metrics table for a project"""
    query = """
    SELECT m.timestamp AT TIME ZONE 'UTC'
    FROM metrics m
    JOIN repositories r ON r.id = m.repository_id
    WHERE r.repo_key = %s
    ORDER BY m.timestamp DESC
    LIMIT 1;
    """
    try:
        result = execute_query(query, (project_key,))
        if result and result[0]:
            return result[0][0]
        return None
    except Exception as e:
        print(f"Error getting last update timestamp: {str(e)}")
        return None

def get_project_update_interval(project_key):
    """Get update interval from repositories table"""
    query = """
    SELECT update_interval
    FROM repositories
    WHERE repo_key = %s;
    """
    try:
        result = execute_query(query, (project_key,))
        if result and result[0]:
            return result[0][0]
        return 3600  # Default to 1 hour
    except Exception as e:
        print(f"Error getting update interval: {str(e)}")
        return 3600

def display_multi_project_metrics(projects_data):
    """Display metrics for multiple projects including inactive ones in a comparative view"""
    st.markdown("""
        <style>
        .project-card {
            background: #1A1F25;
            border: 1px solid #2D3748;
            border-radius: 0.5rem;
            padding: 1rem;
            margin-bottom: 1rem;
        }
        .inactive-project-card {
            background: #1A1F25;
            border: 1px solid #4A5568;
            border-radius: 0.5rem;
            padding: 1rem;
            margin-bottom: 1rem;
            opacity: 0.8;
        }
        .metric-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1rem;
            margin-top: 1rem;
        }
        .metric-item {
            padding: 0.5rem;
            border-radius: 0.25rem;
            background: #2D3748;
        }
        .metric-title {
            color: #A0AEC0;
            font-size: 0.8rem;
        }
        .metric-value {
            color: #FAFAFA;
            font-size: 1.2rem;
            font-weight: bold;
        }
        .totals-card {
            background: #2D3748;
            border-radius: 0.5rem;
            padding: 1rem;
            margin-bottom: 1rem;
        }
        .status-badge {
            display: inline-block;
            padding: 0.25rem 0.5rem;
            border-radius: 0.25rem;
            font-size: 0.8rem;
            margin-left: 0.5rem;
        }
        .inactive-badge {
            background: #4A5568;
            color: #A0AEC0;
        }
        .deleted-badge {
            background: #742A2A;
            color: #FEB2B2;
        }
        </style>
    """, unsafe_allow_html=True)
    
    metrics_processor = MetricsProcessor()
    analyzer = MetricAnalyzer()
    
    # Get all projects including inactive ones
    all_projects = metrics_processor.get_project_status()
    
    # Process active projects data
    metrics_list = []
    for project_key, data in projects_data.items():
        metrics = data['metrics'].copy()
        metrics['project_key'] = project_key
        metrics['project_name'] = data['name']
        metrics['quality_score'] = analyzer.calculate_quality_score(metrics)
        metrics['status'] = 'active'
        metrics['update_interval'] = get_project_update_interval(project_key)
        metrics['last_update'] = get_last_update_timestamp(project_key)
        metrics_list.append(metrics)
    
    # Add inactive projects
    for project in all_projects:
        if not project['is_active'] and project['latest_metrics']:
            metrics = project['latest_metrics'].copy()
            metrics['project_key'] = project['repo_key']
            metrics['project_name'] = project['name']
            metrics['quality_score'] = analyzer.calculate_quality_score(metrics)
            metrics['status'] = 'deleted' if project['is_marked_for_deletion'] else 'inactive'
            metrics['update_interval'] = project.get('update_interval', 3600)
            metrics['last_update'] = project['last_seen']
            metrics['inactive_duration'] = project['inactive_duration']
            metrics_list.append(metrics)
    
    df = pd.DataFrame(metrics_list)
    
    # Calculate totals including inactive projects
    total_lines = df['ncloc'].sum()
    total_debt = df['sqale_index'].sum()
    
    st.markdown(f"""
        <div class="totals-card">
            <h3 style="color: #FAFAFA;">📊 Organization Totals</h3>
            <div class="metric-grid">
                <div class="metric-item">
                    <div class="metric-title">Total Lines of Code</div>
                    <div class="metric-value">{format_code_lines(total_lines)} 📏</div>
                </div>
                <div class="metric-item">
                    <div class="metric-title">Total Technical Debt</div>
                    <div class="metric-value">{format_technical_debt(total_debt)} ⏱️</div>
                </div>
            </div>
        </div>
    """, unsafe_allow_html=True)
    
    df = df.sort_values(['status', 'quality_score'], ascending=[True, False])
    
    for _, row in df.iterrows():
        card_class = "project-card" if row['status'] == 'active' else "inactive-project-card"
        status_badge = ""
        if row['status'] == 'inactive':
            status_badge = '<span class="status-badge inactive-badge">⚠️ Inactive</span>'
        elif row['status'] == 'deleted':
            status_badge = '<span class="status-badge deleted-badge">🗑️ Marked for Deletion</span>'
        
        interval_display = format_update_interval(row['update_interval'])
        last_update_display = format_last_update(row['last_update'])
        
        st.markdown(f"""
            <div class="{card_class}">
                <h3 style="color: #FAFAFA;">{row['project_name']}{status_badge}</h3>
                <p style="color: #A0AEC0;">Quality Score: {row['quality_score']:.1f}/100</p>
                <div style="color: #A0AEC0; font-size: 0.8rem;">
                    <span>⏱️ Update interval: {interval_display}</span>
                    <span> • </span>
                    <span>🕒 {last_update_display}</span>
                    {f'<br><span>⚠️ Inactive for: {row["inactive_duration"].days}d</span>' if row['status'] != 'active' else ''}
                </div>
                <div class="metric-grid">
                    <div class="metric-item">
                        <div class="metric-title">Lines of Code</div>
                        <div class="metric-value">{format_code_lines(row['ncloc'])} 📏</div>
                    </div>
                    <div class="metric-item">
                        <div class="metric-title">Technical Debt</div>
                        <div class="metric-value">{format_technical_debt(row['sqale_index'])} ⏱️</div>
                    </div>
                    <div class="metric-item">
                        <div class="metric-title">Bugs</div>
                        <div class="metric-value">{int(row['bugs'])} 🐛</div>
                    </div>
                    <div class="metric-item">
                        <div class="metric-title">Vulnerabilities</div>
                        <div class="metric-value">{int(row['vulnerabilities'])} ⚠️</div>
                    </div>
                    <div class="metric-item">
                        <div class="metric-title">Code Smells</div>
                        <div class="metric-value">{int(row['code_smells'])} 🔧</div>
                    </div>
                    <div class="metric-item">
                        <div class="metric-title">Coverage</div>
                        <div class="metric-value">{row['coverage']:.1f}% 📊</div>
                    </div>
                    <div class="metric-item">
                        <div class="metric-title">Duplication</div>
                        <div class="metric-value">{row['duplicated_lines_density']:.1f}% 📝</div>
                    </div>
                </div>
            </div>
        """, unsafe_allow_html=True)

def create_download_report(data):
    """Create downloadable CSV report including inactive projects"""
    st.markdown('<h3 style="color: #FAFAFA;">📥 Download Report</h3>', unsafe_allow_html=True)
    
    metrics_processor = MetricsProcessor()
    analyzer = MetricAnalyzer()
    
    # Get all projects including inactive ones
    all_projects = metrics_processor.get_project_status()
    
    # Create DataFrame with both active and inactive projects
    all_data = []
    
    # Add active projects
    if isinstance(data, dict):  # Handle single project case
        df = pd.DataFrame([data])
        df['status'] = 'active'
        all_data.append(df)
    else:  # Handle multiple projects case
        df = pd.DataFrame(data)
        df['status'] = 'active'
        all_data.append(df)
    
    # Add inactive projects
    for project in all_projects:
        if not project['is_active'] and project['latest_metrics']:
            metrics = project['latest_metrics'].copy()
            metrics['status'] = 'deleted' if project['is_marked_for_deletion'] else 'inactive'
            metrics['inactive_duration_days'] = project['inactive_duration'].days if project['inactive_duration'] else 0
            metrics['last_seen'] = project['last_seen']
            df_inactive = pd.DataFrame([metrics])
            all_data.append(df_inactive)
    
    # Combine all data
    final_df = pd.concat(all_data, ignore_index=True)
    
    # Calculate quality scores
    final_df['quality_score'] = final_df.apply(
        lambda row: analyzer.calculate_quality_score(row.to_dict()), 
        axis=1
    )
    
    # Add metric status indicators
    status_df = pd.DataFrame([
        analyzer.get_metric_status(row.to_dict()) 
        for _, row in final_df.iterrows()
    ])
    
    # Format technical debt and lines of code
    if 'sqale_index' in final_df.columns:
        final_df['technical_debt_formatted'] = final_df['sqale_index'].apply(format_technical_debt)
    if 'ncloc' in final_df.columns:
        final_df['lines_of_code_formatted'] = final_df['ncloc'].apply(format_code_lines)
    
    # Combine all data
    final_df = pd.concat([final_df, status_df], axis=1)
    
    csv = final_df.to_csv(index=False)
    st.download_button(
        label="📊 Download Detailed CSV Report",
        data=csv,
        file_name="sonarcloud_metrics_analysis.csv",
        mime="text/csv",
        help="Download a detailed CSV report containing all metrics and historical data for both active and inactive projects"
    )

def display_metric_trends(historical_data):
    """Display metric trends over time"""
    st.markdown('<h3 style="color: #FAFAFA;">📈 Trend Analysis</h3>', unsafe_allow_html=True)
    
    metrics = ['bugs', 'vulnerabilities', 'code_smells', 'coverage', 'duplicated_lines_density', 'ncloc', 'sqale_index']
    analyzer = MetricAnalyzer()
    
    for metric in metrics:
        trend_data = analyzer.calculate_trend(historical_data, metric)
        period_comparison = analyzer.calculate_period_comparison(historical_data, metric)
        
        if trend_data and period_comparison:
            metric_display_name = {
                'ncloc': 'Lines of Code',
                'sqale_index': 'Technical Debt'
            }.get(metric, metric.replace('_', ' ').title())
            
            with st.expander(f"{metric_display_name} Analysis", expanded=True):
                col1, col2 = st.columns(2)
                
                with col1:
                    trend_emoji = "📈" if trend_data['trend'] == 'increasing' else "📉" if trend_data['trend'] == 'decreasing' else "➡️"
                    current_value = (
                        format_code_lines(trend_data['current_value']) if metric == 'ncloc'
                        else format_technical_debt(trend_data['current_value']) if metric == 'sqale_index'
                        else f"{trend_data['current_value']:.2f}"
                    )
                    avg_value = (
                        format_code_lines(trend_data['avg_value']) if metric == 'ncloc'
                        else format_technical_debt(trend_data['avg_value']) if metric == 'sqale_index'
                        else f"{trend_data['avg_value']:.2f}"
                    )
                    
                    st.markdown(f"""
                        <div style='background-color: #1A1F25; padding: 1rem; border-radius: 0.5rem; border: 1px solid #2D3748; box-shadow: 0 1px 3px rgba(0,0,0,0.24);'>
                            <div style='font-size: 0.9rem; color: #A0AEC0;'>Current Trend</div>
                            <div style='font-size: 1.2rem; margin: 0.5rem 0; color: #FAFAFA;'>{trend_emoji} {trend_data['trend'].title()}</div>
                            <div style='font-size: 0.9rem; color: #CBD5E0;'>Current value: {current_value}</div>
                            <div style='font-size: 0.9rem; color: #CBD5E0;'>Average value: {avg_value}</div>
                        </div>
                    """, unsafe_allow_html=True)
                
                with col2:
                    change = period_comparison['change_percentage']
                    is_improvement = (
                        change > 0 if metric == 'ncloc'
                        else change < 0 if metric == 'sqale_index'
                        else period_comparison['improved']
                    )
                    change_color = "#48BB78" if is_improvement else "#F56565"
                    
                    current_period = (
                        format_code_lines(period_comparison['current_period_avg']) if metric == 'ncloc'
                        else format_technical_debt(period_comparison['current_period_avg']) if metric == 'sqale_index'
                        else f"{period_comparison['current_period_avg']:.2f}"
                    )
                    previous_period = (
                        format_code_lines(period_comparison['previous_period_avg']) if metric == 'ncloc'
                        else format_technical_debt(period_comparison['previous_period_avg']) if metric == 'sqale_index'
                        else f"{period_comparison['previous_period_avg']:.2f}"
                    )
                    
                    st.markdown(f"""
                        <div style='background-color: #1A1F25; padding: 1rem; border-radius: 0.5rem; border: 1px solid #2D3748; box-shadow: 0 1px 3px rgba(0,0,0,0.24);'>
                            <div style='font-size: 0.9rem; color: #A0AEC0;'>7-Day Comparison</div>
                            <div style='font-size: 1.2rem; margin: 0.5rem 0; color: {change_color};'>{change:+.1f}%</div>
                            <div style='font-size: 0.9rem; color: #CBD5E0;'>Current period avg: {current_period}</div>
                            <div style='font-size: 0.9rem; color: #CBD5E0;'>Previous period avg: {previous_period}</div>
                        </div>
                    """, unsafe_allow_html=True)
