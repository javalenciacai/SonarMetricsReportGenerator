import streamlit as st
import pandas as pd
from services.metric_analyzer import MetricAnalyzer
from utils.helpers import format_code_lines, format_technical_debt

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
        </style>
    """, unsafe_allow_html=True)

    analyzer = MetricAnalyzer()
    
    # Create a DataFrame for easy comparison
    metrics_list = []
    for project_key, data in projects_data.items():
        metrics = data['metrics']
        metrics['project_key'] = project_key
        metrics['project_name'] = data['name']
        metrics['quality_score'] = analyzer.calculate_quality_score(metrics)
        metrics_list.append(metrics)
    
    df = pd.DataFrame(metrics_list)
    
    # Calculate totals
    total_lines = df['ncloc'].sum()
    total_debt = df['sqale_index'].sum()
    
    # Display totals card
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
    
    # Sort projects by quality score
    df = df.sort_values('quality_score', ascending=False)
    
    # Display project cards
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
    
    # Calculate quality score and status
    analyzer = MetricAnalyzer()
    quality_score = analyzer.calculate_quality_score(metrics_data)
    metric_status = analyzer.get_metric_status(metrics_data)
    
    # Create header with quality score
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
    
    # Display metrics in organized sections
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown('<h4 style="color: #FAFAFA;">📏 Project Size & Debt</h4>', unsafe_allow_html=True)
        ncloc = int(metrics_data.get('ncloc', 0))
        sqale_index = int(metrics_data.get('sqale_index', 0))
        create_metric_card(
            "Lines of Code",
            format_code_lines(ncloc),
            "📏",
            "Total number of lines of code (excluding comments and blank lines)"
        )
        create_metric_card(
            "Technical Debt",
            format_technical_debt(sqale_index),
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
                    # For ncloc and sqale_index, increasing is generally positive and negative respectively
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

def create_download_report(data):
    """Create downloadable CSV report"""
    st.markdown('<h3 style="color: #FAFAFA;">📥 Download Report</h3>', unsafe_allow_html=True)
    df = pd.DataFrame(data)
    
    # Add quality score calculation
    analyzer = MetricAnalyzer()
    df['quality_score'] = df.apply(lambda row: analyzer.calculate_quality_score(row.to_dict()), axis=1)
    
    # Calculate metric status
    status_df = pd.DataFrame([analyzer.get_metric_status(row.to_dict()) 
                           for _, row in df.iterrows()])
    
    # Format technical debt and lines of code
    if 'sqale_index' in df.columns:
        df['technical_debt_formatted'] = df['sqale_index'].apply(format_technical_debt)
    if 'ncloc' in df.columns:
        df['lines_of_code_formatted'] = df['ncloc'].apply(format_code_lines)
    
    # Combine all data
    final_df = pd.concat([df, status_df], axis=1)
    
    csv = final_df.to_csv(index=False)
    st.download_button(
        label="📊 Download Detailed CSV Report",
        data=csv,
        file_name="sonarcloud_metrics_analysis.csv",
        mime="text/csv",
        help="Download a detailed CSV report containing all metrics and their historical data"
    )
