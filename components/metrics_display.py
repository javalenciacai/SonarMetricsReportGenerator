import streamlit as st
import pandas as pd
from services.metric_analyzer import MetricAnalyzer
from utils.helpers import format_code_lines, format_technical_debt
from database.schema import get_update_preferences
from database.connection import execute_query
from datetime import datetime, timezone
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.express as px

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
    """Format last update timestamp in UTC format"""
    if not timestamp:
        return "No updates yet"
    
    try:
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        # Convert to UTC if not already
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        diff = now - timestamp
        
        # Include UTC indicator in display
        if diff.days > 0:
            return f"{diff.days}d ago (UTC)"
        elif diff.seconds >= 3600:
            return f"{diff.seconds//3600}h ago (UTC)"
        elif diff.seconds >= 60:
            return f"{diff.seconds//60}m ago (UTC)"
        return f"{diff.seconds}s ago (UTC)"
    except (ValueError, TypeError) as e:
        print(f"Error formatting timestamp: {str(e)}")
        return "Invalid timestamp"

def display_current_metrics(metrics):
    """Display current metrics with status indicators"""
    analyzer = MetricAnalyzer()
    quality_score = analyzer.calculate_quality_score(metrics)
    
    # Display quality score with status indicator
    status = "🟢" if quality_score >= 80 else "🟡" if quality_score >= 60 else "🔴"
    st.markdown(f"## Quality Score: {status} {quality_score:.1f}/100")
    
    # Create three columns for metrics display
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("### 🛡️ Security & Reliability")
        st.metric("Bugs 🐛", metrics.get('bugs', 0))
        st.metric("Vulnerabilities ⚠️", metrics.get('vulnerabilities', 0))
        st.metric("Code Smells 🔧", metrics.get('code_smells', 0))
    
    with col2:
        st.markdown("### 📊 Coverage & Quality")
        st.metric("Coverage 📈", f"{metrics.get('coverage', 0):.1f}%")
        st.metric("Duplication 📝", f"{metrics.get('duplicated_lines_density', 0):.1f}%")
    
    with col3:
        st.markdown("### 📏 Size & Complexity")
        st.metric("Lines of Code", format_code_lines(metrics.get('ncloc', 0)))
        st.metric("Technical Debt", format_technical_debt(metrics.get('sqale_index', 0)))

def create_download_report(data):
    """Create and offer downloadable CSV report with UTC timestamps"""
    if isinstance(data, dict) and 'metrics' in data:
        # Single project data
        df = pd.DataFrame([data['metrics']])
    elif isinstance(data, list):
        # Historical or multi-project data
        df = pd.DataFrame(data)
    else:
        # Raw metrics data
        df = pd.DataFrame([data])
    
    # Convert timestamps to UTC
    if 'timestamp' in df.columns:
        df['timestamp'] = pd.to_datetime(df['timestamp']).dt.tz_localize('UTC')
        # Add UTC indicator to timestamp column
        df['timestamp'] = df['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S UTC')
    
    # Generate timestamp for filename
    current_time = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_UTC")
    csv = df.to_csv(index=False)
    st.download_button(
        "📥 Download Report",
        csv,
        f"metrics_report_{current_time}.csv",
        "text/csv",
        key='download-csv'
    )

def display_metric_trends(historical_data):
    """Display metric trends with UTC timestamps"""
    if not historical_data:
        st.warning("No historical data available for trend analysis")
        return
    
    df = pd.DataFrame(historical_data)
    df['timestamp'] = pd.to_datetime(df['timestamp']).dt.tz_localize('UTC')
    
    # Calculate 7-day and 30-day moving averages
    for metric in ['bugs', 'vulnerabilities', 'code_smells', 'coverage', 'duplicated_lines_density']:
        if metric in df.columns:
            df[f'{metric}_7d_ma'] = df[metric].rolling(window=7).mean()
            df[f'{metric}_30d_ma'] = df[metric].rolling(window=30).mean()
    
    st.markdown("## 📈 Trend Analysis")
    
    # Calculate and display trends with UTC timestamps
    current = df.iloc[0] if not df.empty else None
    week_ago = df[df['timestamp'] >= df['timestamp'].max() - pd.Timedelta(days=7)].mean()
    
    if current is not None:
        st.markdown(f"### Last Update: {current['timestamp'].strftime('%Y-%m-%d %H:%M:%S UTC')}")
        
        metrics_display = {
            'Bugs': ('bugs', '🐛'),
            'Vulnerabilities': ('vulnerabilities', '⚠️'),
            'Code Smells': ('code_smells', '🔧'),
            'Coverage': ('coverage', '📊'),
            'Duplication': ('duplicated_lines_density', '📝')
        }
        
        for title, (metric, emoji) in metrics_display.items():
            if metric in df.columns:
                current_val = current[metric]
                week_ago_val = week_ago[metric]
                change = ((current_val - week_ago_val) / week_ago_val * 100) if week_ago_val else 0
                
                trend = "📈" if change > 5 else "📉" if change < -5 else "➡️"
                color = "red" if (change > 5 and metric != 'coverage') or (change < -5 and metric == 'coverage') else "green"
                
                st.markdown(f"### {emoji} {title}")
                st.markdown(f"""
                    Current: {current_val:.1f}
                    {trend} {abs(change):.1f}% {'increase' if change > 0 else 'decrease'} over 7 days
                    """)

def display_multi_project_metrics(projects_data):
    """Display metrics for multiple projects with UTC timestamps"""
    if not projects_data:
        st.warning("No project data available")
        return
    
    st.markdown("## 📊 Multi-Project Overview")
    st.markdown(f"Last Updated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    
    # Create a DataFrame for comparison
    data_list = []
    for key, data in projects_data.items():
        metrics = data['metrics']
        metrics['name'] = data['name']
        data_list.append(metrics)
    
    df = pd.DataFrame(data_list)
    
    # Calculate quality scores
    analyzer = MetricAnalyzer()
    df['quality_score'] = df.apply(lambda row: analyzer.calculate_quality_score(row), axis=1)
    
    # Sort by quality score
    df = df.sort_values('quality_score', ascending=False)
    
    # Display project cards
    for _, row in df.iterrows():
        status = "🟢" if row['quality_score'] >= 80 else "🟡" if row['quality_score'] >= 60 else "🔴"
        
        with st.expander(f"{status} {row['name']} - Score: {row['quality_score']:.1f}", expanded=True):
            col1, col2 = st.columns(2)
            
            with col1:
                st.metric("Bugs 🐛", int(row['bugs']))
                st.metric("Vulnerabilities ⚠️", int(row['vulnerabilities']))
                st.metric("Code Smells 🔧", int(row['code_smells']))
            
            with col2:
                st.metric("Coverage 📊", f"{row['coverage']:.1f}%")
                st.metric("Duplication 📝", f"{row['duplicated_lines_density']:.1f}%")
                st.metric("Lines of Code 📏", format_code_lines(row['ncloc']))
    
    # Create downloadable report
    create_download_report(data_list)
