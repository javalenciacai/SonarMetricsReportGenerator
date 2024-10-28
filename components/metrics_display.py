import streamlit as st
import pandas as pd
from services.metric_analyzer import MetricAnalyzer

def display_current_metrics(metrics_data):
    st.subheader("Current Metrics")
    
    # Calculate quality score and status
    quality_score = MetricAnalyzer.calculate_quality_score(metrics_data)
    metric_status = MetricAnalyzer.get_metric_status(metrics_data)
    
    # Display overall quality score
    st.metric("Overall Quality Score", f"{quality_score:.1f}/100")
    
    # Display individual metrics with status indicators
    cols = st.columns(5)
    metrics = [
        ('bugs', 'Bugs'),
        ('vulnerabilities', 'Vulnerabilities'),
        ('code_smells', 'Code Smells'),
        ('coverage', 'Coverage'),
        ('duplicated_lines_density', 'Duplicated Lines')
    ]
    
    for i, (metric_key, metric_label) in enumerate(metrics):
        with cols[i]:
            value = metrics_data.get(metric_key, 0)
            status = metric_status.get(metric_key, 'neutral')
            
            # Add status emoji
            emoji = "🟢" if status == 'good' else "🟡" if status == 'warning' else "🔴"
            
            # Format value based on metric type
            if metric_key in ['coverage', 'duplicated_lines_density']:
                formatted_value = f"{value}%"
            else:
                formatted_value = str(int(value))
                
            st.metric(
                f"{emoji} {metric_label}",
                formatted_value
            )

def display_metric_trends(historical_data):
    st.subheader("Metric Trends Analysis")
    
    metrics = ['bugs', 'vulnerabilities', 'code_smells', 'coverage', 'duplicated_lines_density']
    analyzer = MetricAnalyzer()
    
    for metric in metrics:
        trend_data = analyzer.calculate_trend(historical_data, metric)
        period_comparison = analyzer.calculate_period_comparison(historical_data, metric)
        
        if trend_data and period_comparison:
            col1, col2 = st.columns(2)
            
            with col1:
                st.write(f"**{metric.replace('_', ' ').title()}**")
                trend_emoji = "📈" if trend_data['trend'] == 'increasing' else "📉" if trend_data['trend'] == 'decreasing' else "➡️"
                st.write(f"Trend: {trend_emoji} {trend_data['trend']}")
                st.write(f"Current value: {trend_data['current_value']:.2f}")
                st.write(f"Average value: {trend_data['avg_value']:.2f}")
            
            with col2:
                change = period_comparison['change_percentage']
                change_color = "green" if period_comparison['improved'] else "red"
                st.write("**7-Day Comparison**")
                st.markdown(f"Change: <span style='color: {change_color}'>{change:+.1f}%</span>", unsafe_allow_html=True)
                st.write(f"Current period avg: {period_comparison['current_period_avg']:.2f}")
                st.write(f"Previous period avg: {period_comparison['previous_period_avg']:.2f}")

def create_download_report(data):
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
        label="Download Detailed CSV Report",
        data=csv,
        file_name="sonarcloud_metrics_analysis.csv",
        mime="text/csv"
    )
