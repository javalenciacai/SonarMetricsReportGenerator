import streamlit as st
import pandas as pd
from services.metric_analyzer import MetricAnalyzer

def create_metric_card(title, value, status, help_text):
    """Create a styled metric card with help tooltip"""
    st.markdown(f"""
        <div style="
            padding: 1rem;
            border-radius: 0.5rem;
            background: white;
            box-shadow: 0 1px 3px rgba(0,0,0,0.12);
            margin-bottom: 1rem;">
            <div style="color: #666; font-size: 0.8rem;">{title}</div>
            <div style="font-size: 1.5rem; font-weight: bold; margin: 0.5rem 0;">
                {value} {status}
            </div>
        </div>
    """, unsafe_allow_html=True)
    if help_text:
        st.markdown(f"<small>{help_text}</small>", unsafe_allow_html=True)

def display_current_metrics(metrics_data):
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
            color: #262730;
        }
        .trend-positive { color: #28a745; }
        .trend-negative { color: #dc3545; }
        .trend-neutral { color: #6c757d; }
        </style>
    """, unsafe_allow_html=True)
    
    # Calculate quality score and status
    quality_score = MetricAnalyzer.calculate_quality_score(metrics_data)
    metric_status = MetricAnalyzer.get_metric_status(metrics_data)
    
    # Create header with quality score
    col1, col2 = st.columns([2, 1])
    with col1:
        st.markdown("### Executive Dashboard")
        st.markdown("Real-time code quality metrics and insights")
    with col2:
        st.markdown(f"""
            <div style="text-align: right;">
                <div style="font-size: 0.9rem; color: #666;">Overall Quality Score</div>
                <div class="big-number">{quality_score:.1f}</div>
                <div style="font-size: 0.8rem; color: #666;">out of 100</div>
            </div>
        """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Display metrics in organized sections
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("#### 🛡️ Security & Reliability")
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
    
    with col2:
        st.markdown("#### 🔍 Code Quality")
        code_smells = int(metrics_data.get('code_smells', 0))
        duplications = f"{metrics_data.get('duplicated_lines_density', 0):.1f}%"
        create_metric_card(
            "Code Smells",
            code_smells,
            "🔧" if code_smells > 0 else "✅",
            "Maintainability issues that might lead to bugs"
        )
        create_metric_card(
            "Code Duplication",
            duplications,
            "📝",
            "Percentage of duplicated lines in the codebase"
        )
    
    with col3:
        st.markdown("#### 📊 Test Coverage")
        coverage = f"{metrics_data.get('coverage', 0):.1f}%"
        coverage_status = metric_status.get('coverage', 'neutral')
        create_metric_card(
            "Test Coverage",
            coverage,
            "🟢" if coverage_status == 'good' else "🟡" if coverage_status == 'warning' else "🔴",
            "Percentage of code covered by unit tests"
        )

def display_metric_trends(historical_data):
    st.markdown("### 📈 Trend Analysis")
    
    metrics = ['bugs', 'vulnerabilities', 'code_smells', 'coverage', 'duplicated_lines_density']
    analyzer = MetricAnalyzer()
    
    for metric in metrics:
        trend_data = analyzer.calculate_trend(historical_data, metric)
        period_comparison = analyzer.calculate_period_comparison(historical_data, metric)
        
        if trend_data and period_comparison:
            with st.expander(f"{metric.replace('_', ' ').title()} Analysis", expanded=True):
                col1, col2 = st.columns(2)
                
                with col1:
                    trend_emoji = "📈" if trend_data['trend'] == 'increasing' else "📉" if trend_data['trend'] == 'decreasing' else "➡️"
                    st.markdown(f"""
                        <div style='background-color: white; padding: 1rem; border-radius: 0.5rem; box-shadow: 0 1px 3px rgba(0,0,0,0.12);'>
                            <div style='font-size: 0.9rem; color: #666;'>Current Trend</div>
                            <div style='font-size: 1.2rem; margin: 0.5rem 0;'>{trend_emoji} {trend_data['trend'].title()}</div>
                            <div style='font-size: 0.9rem;'>Current value: {trend_data['current_value']:.2f}</div>
                            <div style='font-size: 0.9rem;'>Average value: {trend_data['avg_value']:.2f}</div>
                        </div>
                    """, unsafe_allow_html=True)
                
                with col2:
                    change = period_comparison['change_percentage']
                    change_color = "green" if period_comparison['improved'] else "red"
                    st.markdown(f"""
                        <div style='background-color: white; padding: 1rem; border-radius: 0.5rem; box-shadow: 0 1px 3px rgba(0,0,0,0.12);'>
                            <div style='font-size: 0.9rem; color: #666;'>7-Day Comparison</div>
                            <div style='font-size: 1.2rem; margin: 0.5rem 0; color: {change_color};'>{change:+.1f}%</div>
                            <div style='font-size: 0.9rem;'>Current period avg: {period_comparison['current_period_avg']:.2f}</div>
                            <div style='font-size: 0.9rem;'>Previous period avg: {period_comparison['previous_period_avg']:.2f}</div>
                        </div>
                    """, unsafe_allow_html=True)

def create_download_report(data):
    st.markdown("### 📥 Download Report")
    df = pd.DataFrame(data)
    
    # Add quality score calculation
    metrics_dict = df.iloc[-1].to_dict()
    quality_score = MetricAnalyzer.calculate_quality_score(metrics_dict)
    df['quality_score'] = df.apply(lambda row: MetricAnalyzer.calculate_quality_score(row.to_dict()), axis=1)
    
    # Calculate metric status
    status_df = pd.DataFrame([MetricAnalyzer.get_metric_status(row.to_dict()) 
                           for _, row in df.iterrows()])
    
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
