import streamlit as st
import pandas as pd
from services.metric_analyzer import MetricAnalyzer
from utils.helpers import format_code_lines, format_technical_debt
from database.schema import get_update_preferences
from database.connection import execute_query
from datetime import datetime, timezone, timedelta
import plotly.graph_objects as go
from plotly.subplots import make_subplots

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

def display_current_metrics(metrics_data):
    """Display current metrics for a single project"""
    st.markdown("""
        <style>
        .metric-row {
            display: flex;
            justify-content: space-between;
            flex-wrap: wrap;
            gap: 1rem;
            margin-bottom: 2rem;
        }
        .big-number {
            font-size: 2.5rem;
            font-weight: bold;
            color: #FAFAFA;
        }
        .trend-positive { color: #48BB78; }
        .trend-negative { color: #F56565; }
        .trend-neutral { color: #A0AEC0; }
        .stMarkdown {
            color: #FAFAFA;
        }
        </style>
    """, unsafe_allow_html=True)
    
    analyzer = MetricAnalyzer()
    quality_score = analyzer.calculate_quality_score(metrics_data)
    metric_status = analyzer.get_metric_status(metrics_data)
    
    col1, col2 = st.columns([2, 1])
    with col1:
        st.markdown('<h3 style="color: #FAFAFA;">Executive Dashboard</h3>', unsafe_allow_html=True)
        st.markdown('<p style="color: #A0AEC0;">Real-time code quality metrics and insights</p>', unsafe_allow_html=True)
    with col2:
        st.markdown(f"""
            <div style="text-align: right;">
                <div style="font-size: 0.9rem; color: #A0AEC0;">Overall Quality Score</div>
                <div class="big-number">{quality_score:.1f}</div>
                <div style="font-size: 0.8rem; color: #A0AEC0;">out of 100</div>
            </div>
        """, unsafe_allow_html=True)
    
    st.markdown('<hr style="border-color: #2D3748;">', unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown('<h4 style="color: #FAFAFA;">📏 Project Size & Debt</h4>', unsafe_allow_html=True)
        create_metric_card(
            "Lines of Code",
            format_code_lines(metrics_data.get('ncloc', 0)),
            "📏",
            "Total number of lines of code (excluding comments and blank lines)"
        )
        create_metric_card(
            "Technical Debt",
            format_technical_debt(metrics_data.get('sqale_index', 0)),
            "⏱️",
            "Estimated time to fix all code smells"
        )

    with col2:
        st.markdown('<h4 style="color: #FAFAFA;">🛡️ Security & Reliability</h4>', unsafe_allow_html=True)
        bugs = int(metrics_data.get('bugs', 0))
        vulnerabilities = int(metrics_data.get('vulnerabilities', 0))
        create_metric_card(
            "Bugs",
            bugs,
            "🐛" if bugs > 0 else "✅",
            "Number of reliability issues found in the code"
        )
        create_metric_card(
            "Vulnerabilities",
            vulnerabilities,
            "⚠️" if vulnerabilities > 0 else "✅",
            "Number of security vulnerabilities detected"
        )
    
    with col3:
        st.markdown('<h4 style="color: #FAFAFA;">🔍 Code Quality</h4>', unsafe_allow_html=True)
        code_smells = int(metrics_data.get('code_smells', 0))
        coverage = f"{metrics_data.get('coverage', 0):.1f}%"
        duplications = f"{metrics_data.get('duplicated_lines_density', 0):.1f}%"
        coverage_status = metric_status.get('coverage', 'neutral')
        
        create_metric_card(
            "Code Smells",
            code_smells,
            "🔧" if code_smells > 0 else "✅",
            "Maintainability issues that might lead to bugs"
        )
        create_metric_card(
            "Test Coverage",
            coverage,
            "🟢" if coverage_status == 'good' else "🟡" if coverage_status == 'warning' else "🔴",
            "Percentage of code covered by unit tests"
        )
        create_metric_card(
            "Code Duplication",
            duplications,
            "📝",
            "Percentage of duplicated lines in the codebase"
        )

def create_metric_card(title, value, status, help_text):
    """Create a styled metric card with help tooltip"""
    st.markdown(f"""
        <div style="
            padding: 1rem;
            border-radius: 0.5rem;
            background: #1A1F25;
            border: 1px solid #2D3748;
            box-shadow: 0 1px 3px rgba(0,0,0,0.24);
            margin-bottom: 1rem;">
            <div style="color: #A0AEC0; font-size: 0.8rem;">{title}</div>
            <div style="font-size: 1.5rem; font-weight: bold; margin: 0.5rem 0; color: #FAFAFA;">
                {value} {status}
            </div>
        </div>
    """, unsafe_allow_html=True)
    if help_text:
        st.markdown(f'<small style="color: #A0AEC0;">{help_text}</small>', unsafe_allow_html=True)

def create_download_report(data):
    """Create downloadable CSV report"""
    st.markdown('<h3 style="color: #FAFAFA;">📥 Download Report</h3>', unsafe_allow_html=True)
    df = pd.DataFrame(data)
    
    analyzer = MetricAnalyzer()
    df['quality_score'] = df.apply(lambda row: analyzer.calculate_quality_score(row.to_dict()), axis=1)
    
    status_df = pd.DataFrame([analyzer.get_metric_status(row.to_dict()) 
                           for _, row in df.iterrows()])
    
    if 'sqale_index' in df.columns:
        df['technical_debt_formatted'] = df['sqale_index'].apply(format_technical_debt)
    if 'ncloc' in df.columns:
        df['lines_of_code_formatted'] = df['ncloc'].apply(format_code_lines)
    
    final_df = pd.concat([df, status_df], axis=1)
    
    csv = final_df.to_csv(index=False)
    st.download_button(
        label="📊 Download Detailed CSV Report",
        data=csv,
        file_name="sonarcloud_metrics_analysis.csv",
        mime="text/csv",
        help="Download a detailed CSV report containing all metrics and their historical data"
    )

def display_multi_project_metrics(projects_data):
    """Display metrics for multiple projects in a comparative view"""
    st.markdown("""
        <style>
        .project-card {
            background: #1A1F25;
            border: 1px solid #2D3748;
            border-radius: 0.5rem;
            padding: 1rem;
            margin-bottom: 1rem;
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
        .update-interval {
            color: #A0AEC0;
            font-size: 0.8rem;
            margin-top: 0.5rem;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }
        .project-status {
            display: inline-block;
            padding: 0.25rem 0.5rem;
            border-radius: 0.25rem;
            font-size: 0.8rem;
            margin-left: 0.5rem;
        }
        .status-active {
            background: #2F855A;
            color: #FAFAFA;
        }
        .status-inactive {
            background: #C53030;
            color: #FAFAFA;
        }
        </style>
    """, unsafe_allow_html=True)

    analyzer = MetricAnalyzer()
    
    # Calculate total metrics including all projects
    total_metrics = {
        'ncloc': 0,
        'bugs': 0,
        'vulnerabilities': 0,
        'code_smells': 0,
        'sqale_index': 0
    }
    
    # Process all projects and calculate totals
    metrics_list = []
    for project_key, project_info in projects_data.items():
        if project_key == 'all':  # Skip the "All Projects" option
            continue
            
        # Initialize base metrics if they don't exist
        if project_info.get('metrics') is None:
            metrics = {
                'project_key': project_key,
                'project_name': project_info['display_name'],
                'is_active': project_info['is_active'],
                'bugs': 0,
                'vulnerabilities': 0,
                'code_smells': 0,
                'coverage': 0,
                'duplicated_lines_density': 0,
                'ncloc': 0,
                'sqale_index': 0
            }
        else:
            metrics = project_info['metrics'].copy()
            metrics['project_key'] = project_key
            metrics['project_name'] = project_info['display_name']
            metrics['is_active'] = project_info['is_active']
            
            # Add to totals for projects with metrics
            for metric in total_metrics.keys():
                if metric in metrics:
                    total_metrics[metric] += float(metrics[metric])
        
        # Add quality score
        metrics['quality_score'] = analyzer.calculate_quality_score(metrics)
        
        # Get update interval and last update
        metrics['update_interval'] = get_project_update_interval(project_key)
        metrics['last_update'] = get_last_update_timestamp(project_key)
        
        metrics_list.append(metrics)
    
    # Display organization totals
    st.markdown(f"""
        <div class="totals-card">
            <h3 style="color: #FAFAFA;">📊 Organization Totals</h3>
            <div class="metric-grid">
                <div class="metric-item">
                    <div class="metric-title">Total Lines of Code</div>
                    <div class="metric-value">{format_code_lines(total_metrics['ncloc'])} 📏</div>
                </div>
                <div class="metric-item">
                    <div class="metric-title">Total Technical Debt</div>
                    <div class="metric-value">{format_technical_debt(total_metrics['sqale_index'])} ⏱️</div>
                </div>
                <div class="metric-item">
                    <div class="metric-title">Total Issues</div>
                    <div class="metric-value">
                        🐛 {int(total_metrics['bugs'])} 
                        ⚠️ {int(total_metrics['vulnerabilities'])} 
                        🔧 {int(total_metrics['code_smells'])}
                    </div>
                </div>
            </div>
        </div>
    """, unsafe_allow_html=True)
    
    # Sort projects by quality score
    df = pd.DataFrame(metrics_list)
    if not df.empty:
        df = df.sort_values('quality_score', ascending=False)
    
    # Display individual project cards
    for _, row in df.iterrows():
        status_icon = "🗑️" if row.get('is_marked_for_deletion') else "⚠️" if not row['is_active'] else "✅"
        status_class = "status-active" if row['is_active'] else "status-inactive"
        status_text = "Active" if row['is_active'] else "Inactive"
        
        interval_display = format_update_interval(row['update_interval'])
        last_update_display = format_last_update(row['last_update'])
        
        st.markdown(f"""
            <div class="project-card">
                <h3 style="color: #FAFAFA;">
                    {status_icon} {row['project_name']}
                    <span class="project-status {status_class}">{status_text}</span>
                </h3>
                <p style="color: #A0AEC0;">Quality Score: {row['quality_score']:.1f}/100</p>
                <div class="update-interval">
                    <span>⏱️ Update interval: {interval_display}</span>
                    <span>•</span>
                    <span>🕒 {last_update_display}</span>
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

def display_metric_trends(historical_data):
    """Display metric trends over time"""
    if not historical_data:
        st.warning("No historical data available for trend analysis")
        return
    
    st.markdown('<h3 style="color: #FAFAFA;">📈 Trend Analysis</h3>', unsafe_allow_html=True)
    
    # Convert historical data to DataFrame
    df = pd.DataFrame(historical_data)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df = df.sort_values('timestamp')
    
    # Calculate trends
    for metric in ['bugs', 'vulnerabilities', 'code_smells', 'coverage']:
        if metric in df.columns:
            current = df[metric].iloc[-1]
            previous = df[metric].iloc[-2] if len(df) > 1 else current
            change = ((current - previous) / previous * 100) if previous != 0 else 0
            
            direction = "improving" if (metric == 'coverage' and change > 0) or \
                                    (metric != 'coverage' and change < 0) else \
                       "deteriorating" if change != 0 else "stable"
            
            color = "#48BB78" if direction == "improving" else \
                    "#F56565" if direction == "deteriorating" else \
                    "#A0AEC0"
            
            emoji = "📈" if change > 0 else "📉" if change < 0 else "➡️"
            
            st.markdown(f"""
                <div style="
                    background: #1A1F25;
                    border: 1px solid #2D3748;
                    border-radius: 0.5rem;
                    padding: 1rem;
                    margin-bottom: 1rem;
                ">
                    <div style="color: #A0AEC0;">{metric.replace('_', ' ').title()}</div>
                    <div style="
                        font-size: 1.2rem;
                        font-weight: bold;
                        color: {color};
                        margin: 0.5rem 0;
                    ">
                        {direction.title()} {emoji} ({change:+.1f}%)
                    </div>
                    <div style="color: #A0AEC0;">
                        Current: {current:.1f} • Previous: {previous:.1f}
                    </div>
                </div>
            """, unsafe_allow_html=True)
