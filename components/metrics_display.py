import streamlit as st
import pandas as pd
from services.metric_analyzer import MetricAnalyzer
from utils.helpers import format_code_lines, format_technical_debt, format_timestamp
from datetime import datetime, timezone

def format_last_update(timestamp):
    """Format last update timestamp in a human-readable way"""
    if not timestamp:
        return "No updates yet"
    
    try:
        from datetime import datetime, timezone

        # Convert string timestamp to datetime if needed
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        
        # Ensure timestamp is UTC
        if timestamp.tzinfo is None:
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

def display_current_metrics(metrics_data):
    """Display current metrics with status indicators"""
    st.markdown('<h3 style="color: #FAFAFA;">📊 Current Metrics</h3>', unsafe_allow_html=True)
    
    analyzer = MetricAnalyzer()
    quality_score = analyzer.calculate_quality_score(metrics_data)
    metric_status = analyzer.get_metric_status(metrics_data)
    
    col1, col2 = st.columns([2, 1])
    with col1:
        st.markdown('<h4 style="color: #FAFAFA;">Project Overview</h4>', unsafe_allow_html=True)
    with col2:
        st.markdown(f"""
            <div style="text-align: right;">
                <div style="font-size: 0.9rem; color: #A0AEC0;">Quality Score</div>
                <div style="font-size: 2.5rem; font-weight: bold; color: #FAFAFA;">{quality_score:.1f}</div>
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

def display_metric_trends(historical_data):
    """Display trend information for metrics"""
    if not historical_data:
        st.warning("No historical data available for trend analysis")
        return

    analyzer = MetricAnalyzer()
    
    st.markdown('<h3 style="color: #FAFAFA;">📈 Trend Analysis</h3>', unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown('<h4 style="color: #FAFAFA;">Quality Metrics</h4>', unsafe_allow_html=True)
        quality_metrics = ['coverage', 'duplicated_lines_density']
        for metric in quality_metrics:
            if metric in historical_data[0]:
                trend_info = analyzer.calculate_trend(historical_data, metric)
                comparison = analyzer.calculate_period_comparison(historical_data, metric)
                
                if trend_info and comparison:
                    display_trend_card(
                        metric.replace('_', ' ').title(),
                        trend_info,
                        comparison,
                        True
                    )
    
    with col2:
        st.markdown('<h4 style="color: #FAFAFA;">Issue Metrics</h4>', unsafe_allow_html=True)
        issue_metrics = ['bugs', 'vulnerabilities', 'code_smells']
        for metric in issue_metrics:
            if metric in historical_data[0]:
                trend_info = analyzer.calculate_trend(historical_data, metric)
                comparison = analyzer.calculate_period_comparison(historical_data, metric)
                
                if trend_info and comparison:
                    display_trend_card(
                        metric.title(),
                        trend_info,
                        comparison,
                        False
                    )

def display_trend_card(metric_name, trend_info, comparison, higher_is_better):
    """Display a trend analysis card for a metric"""
    trend_emoji = "📈" if trend_info['trend'] == 'increasing' else "📉" if trend_info['trend'] == 'decreasing' else "➡️"
    change = comparison['change_percentage']
    
    is_improvement = (
        (change > 0) if higher_is_better
        else (change < 0)
    )
    
    change_color = "#48BB78" if is_improvement else "#F56565"
    
    st.markdown(f"""
        <div style="
            padding: 1rem;
            border-radius: 0.5rem;
            background: #1A1F25;
            border: 1px solid #2D3748;
            margin-bottom: 1rem;">
            <div style="font-size: 1.1rem; color: #FAFAFA; margin-bottom: 0.5rem;">
                {metric_name}
            </div>
            <div style="display: flex; justify-content: space-between;">
                <div>
                    <div style="color: #A0AEC0; font-size: 0.9rem;">Current Trend</div>
                    <div style="font-size: 1.1rem; color: #FAFAFA;">
                        {trend_emoji} {trend_info['trend'].title()}
                    </div>
                </div>
                <div style="text-align: right;">
                    <div style="color: #A0AEC0; font-size: 0.9rem;">7-Day Change</div>
                    <div style="font-size: 1.1rem; color: {change_color};">
                        {change:+.1f}%
                    </div>
                </div>
            </div>
        </div>
    """, unsafe_allow_html=True)

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
        </style>
    """, unsafe_allow_html=True)
    
    analyzer = MetricAnalyzer()
    
    metrics_list = []
    for project_key, data in projects_data.items():
        metrics = data['metrics']
        metrics['project_key'] = project_key
        metrics['project_name'] = data['name']
        metrics['quality_score'] = analyzer.calculate_quality_score(metrics)
        metrics_list.append(metrics)
    
    df = pd.DataFrame(metrics_list)
    
    total_lines = df['ncloc'].sum()
    total_debt = df['sqale_index'].sum()
    
    st.markdown(f"""
        <div style="background: #2D3748; border-radius: 0.5rem; padding: 1rem; margin-bottom: 1rem;">
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
    
    df = df.sort_values('quality_score', ascending=False)
    
    for _, row in df.iterrows():
        st.markdown(f"""
            <div class="project-card">
                <h3 style="color: #FAFAFA;">{row['project_name']}</h3>
                <p style="color: #A0AEC0;">Quality Score: {row['quality_score']:.1f}/100</p>
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
