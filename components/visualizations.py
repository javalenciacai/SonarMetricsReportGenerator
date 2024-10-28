import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import streamlit as st
from datetime import datetime, timedelta
import numpy as np
from services.metric_analyzer import MetricAnalyzer

def format_code_lines(lines):
    """Format lines of code with K/M suffixes"""
    if lines >= 1_000_000:
        return f"{lines/1_000_000:.1f}M"
    elif lines >= 1_000:
        return f"{lines/1_000:.1f}K"
    return str(int(lines))

def calculate_moving_averages(df, metric_columns, windows=[7, 30]):
    """Calculate moving averages for specified metrics"""
    result_df = df.copy()
    for col in metric_columns:
        for window in windows:
            result_df[f'{col}_ma_{window}d'] = df[col].rolling(window=window).mean()
    return result_df

def calculate_percentage_changes(df, metric_columns, periods=[7, 30]):
    """Calculate percentage changes over different periods"""
    changes = {}
    for col in metric_columns:
        for period in periods:
            changes[f'{col}_{period}d_change'] = (
                (df[col].iloc[-1] - df[col].iloc[-period]) / df[col].iloc[-period] * 100
                if len(df) >= period else None
            )
    return changes

def plot_metrics_history(historical_data):
    """Plot historical metrics data"""
    if not historical_data:
        st.warning("No historical data available")
        return

    df = pd.DataFrame(historical_data)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df = df.sort_values('timestamp')

    # Define metric groups
    issue_metrics = ['bugs', 'vulnerabilities', 'code_smells']
    quality_metrics = ['coverage', 'duplicated_lines_density']
    size_metrics = ['ncloc']
    
    try:
        # Calculate moving averages
        ma_df = calculate_moving_averages(df, issue_metrics + quality_metrics + size_metrics)
        
        # Calculate trend changes
        changes = calculate_percentage_changes(df, issue_metrics + quality_metrics + size_metrics)

        # Dark mode compatible colors
        colors = {
            'bugs': '#F56565',  # Red
            'vulnerabilities': '#ED8936',  # Orange
            'code_smells': '#9F7AEA',  # Purple
            'coverage': '#48BB78',  # Green
            'duplicated_lines_density': '#4299E1',  # Blue
            'ncloc': '#805AD5'  # Purple
        }

        plot_template = {
            'paper_bgcolor': '#1A1F25',
            'plot_bgcolor': '#1A1F25',
            'font': {'color': '#FAFAFA'},
            'xaxis': {
                'gridcolor': '#2D3748',
                'linecolor': '#2D3748'
            },
            'yaxis': {
                'gridcolor': '#2D3748',
                'linecolor': '#2D3748'
            }
        }

        # Lines of Code Plot
        fig_size = go.Figure()
        
        fig_size.add_trace(go.Scatter(
            x=df['timestamp'],
            y=df['ncloc'],
            name='Lines of Code',
            line=dict(color=colors['ncloc'])
        ))
        fig_size.add_trace(go.Scatter(
            x=df['timestamp'],
            y=ma_df['ncloc_ma_7d'],
            name='Lines of Code (7d MA)',
            line=dict(color=colors['ncloc'], dash='dot')
        ))

        fig_size.update_layout(
            title='Project Size Trend Analysis',
            xaxis_title='Date',
            yaxis_title='Lines of Code',
            hovermode='x unified',
            showlegend=True,
            legend=dict(
                yanchor="top",
                y=0.99,
                xanchor="left",
                x=0.01,
                bgcolor='rgba(26, 31, 37, 0.8)',
                bordercolor='#2D3748'
            ),
            **plot_template
        )
        st.plotly_chart(fig_size, use_container_width=True)

        # Issues Plot
        fig1 = go.Figure()
        
        for metric in issue_metrics:
            fig1.add_trace(go.Scatter(
                x=df['timestamp'],
                y=df[metric],
                name=metric.replace('_', ' ').title(),
                line=dict(color=colors[metric])
            ))
            fig1.add_trace(go.Scatter(
                x=df['timestamp'],
                y=ma_df[f'{metric}_ma_7d'],
                name=f'{metric.title()} (7d MA)',
                line=dict(color=colors[metric], dash='dot')
            ))

        fig1.update_layout(
            title='Issues Trend Analysis',
            xaxis_title='Date',
            yaxis_title='Count',
            hovermode='x unified',
            showlegend=True,
            legend=dict(
                yanchor="top",
                y=0.99,
                xanchor="left",
                x=0.01,
                bgcolor='rgba(26, 31, 37, 0.8)',
                bordercolor='#2D3748'
            ),
            **plot_template
        )
        st.plotly_chart(fig1, use_container_width=True)

        # Quality Metrics Plot
        fig2 = go.Figure()
        
        for metric in quality_metrics:
            fig2.add_trace(go.Scatter(
                x=df['timestamp'],
                y=df[metric],
                name=metric.replace('_', ' ').title(),
                line=dict(color=colors[metric])
            ))
            fig2.add_trace(go.Scatter(
                x=df['timestamp'],
                y=ma_df[f'{metric}_ma_7d'],
                name=f'{metric.title()} (7d MA)',
                line=dict(color=colors[metric], dash='dot')
            ))

        fig2.update_layout(
            title='Quality Metrics Trend Analysis',
            xaxis_title='Date',
            yaxis_title='Percentage',
            hovermode='x unified',
            showlegend=True,
            legend=dict(
                yanchor="top",
                y=0.99,
                xanchor="left",
                x=0.01,
                bgcolor='rgba(26, 31, 37, 0.8)',
                bordercolor='#2D3748'
            ),
            **plot_template
        )
        st.plotly_chart(fig2, use_container_width=True)

        # Display trend summary
        st.markdown('<h3 style="color: #FAFAFA;">Trend Summary</h3>', unsafe_allow_html=True)
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown('<p style="color: #FAFAFA;"><strong>Project Size Changes (7 days)</strong></p>', unsafe_allow_html=True)
            change = changes.get('ncloc_7d_change')
            if change is not None:
                emoji = "📈" if change > 0 else "📉" if change < 0 else "➡️"
                color = "#48BB78" if change > 0 else "#F56565" if change < 0 else "#A0AEC0"
                st.markdown(
                    f'<p style="color: #FAFAFA;">Lines of Code: '
                    f'<span style="color: {color}">{change:+.1f}% {emoji}</span></p>',
                    unsafe_allow_html=True
                )

        with col2:
            st.markdown('<p style="color: #FAFAFA;"><strong>Issue Metrics Changes (7 days)</strong></p>', unsafe_allow_html=True)
            for metric in issue_metrics:
                change = changes.get(f'{metric}_7d_change')
                if change is not None:
                    emoji = "📉" if change < 0 else "📈" if change > 0 else "➡️"
                    color = "#48BB78" if change < 0 else "#F56565" if change > 0 else "#A0AEC0"
                    st.markdown(
                        f'<p style="color: #FAFAFA;">{metric.replace("_", " ").title()}: '
                        f'<span style="color: {color}">{change:+.1f}% {emoji}</span></p>',
                        unsafe_allow_html=True
                    )

        with col3:
            st.markdown('<p style="color: #FAFAFA;"><strong>Quality Metrics Changes (7 days)</strong></p>', unsafe_allow_html=True)
            for metric in quality_metrics:
                change = changes.get(f'{metric}_7d_change')
                if change is not None:
                    emoji = "📈" if change > 0 else "📉" if change < 0 else "➡️"
                    color = "#48BB78" if change > 0 else "#F56565" if change < 0 else "#A0AEC0"
                    st.markdown(
                        f'<p style="color: #FAFAFA;">{metric.replace("_", " ").title()}: '
                        f'<span style="color: {color}">{change:+.1f}% {emoji}</span></p>',
                        unsafe_allow_html=True
                    )

    except Exception as e:
        st.error(f"Error plotting metrics: {str(e)}")

def plot_multi_project_comparison(projects_data):
    """Create comparative visualizations for multiple projects"""
    if not projects_data:
        st.warning("No project data available for comparison")
        return

    analyzer = MetricAnalyzer()
    
    # Convert data to DataFrame for easier plotting
    metrics_list = []
    for project_key, data in projects_data.items():
        metrics = data['metrics']
        metrics['project_key'] = project_key
        metrics['project_name'] = data['name']
        metrics_list.append(metrics)
    
    df = pd.DataFrame(metrics_list)

    # Dark mode compatible colors and template
    colors = px.colors.qualitative.Set3
    plot_template = {
        'paper_bgcolor': '#1A1F25',
        'plot_bgcolor': '#1A1F25',
        'font': {'color': '#FAFAFA'},
        'xaxis': {
            'gridcolor': '#2D3748',
            'linecolor': '#2D3748'
        },
        'yaxis': {
            'gridcolor': '#2D3748',
            'linecolor': '#2D3748'
        }
    }

    # Project Size Comparison
    st.markdown("### 📏 Project Size Comparison")
    
    fig_size = go.Figure()
    fig_size.add_trace(go.Bar(
        x=df['project_name'],
        y=df['ncloc'],
        name='Lines of Code',
        marker_color='#805AD5',
        text=[format_code_lines(val) for val in df['ncloc']],
        textposition='outside'
    ))
    fig_size.update_layout(
        title='Lines of Code by Project',
        xaxis_title='Project',
        yaxis_title='Lines of Code',
        **plot_template
    )
    st.plotly_chart(fig_size, use_container_width=True)

    # Quality Score Bar Chart
    st.markdown("### 📊 Quality Metrics Comparison")
    
    fig1 = go.Figure()
    fig1.add_trace(go.Bar(
        x=df['project_name'],
        y=df.apply(lambda row: analyzer.calculate_quality_score(row), axis=1),
        name='Quality Score',
        marker_color='#48BB78'
    ))
    fig1.update_layout(
        title='Overall Quality Score by Project',
        xaxis_title='Project',
        yaxis_title='Quality Score',
        **plot_template
    )
    st.plotly_chart(fig1, use_container_width=True)

    # Issues Comparison
    st.markdown("### 🐛 Issues Comparison")
    
    # Create a grouped bar chart for issues
    issue_metrics = ['bugs', 'vulnerabilities', 'code_smells']
    fig2 = go.Figure()
    
    for i, metric in enumerate(issue_metrics):
        fig2.add_trace(go.Bar(
            name=metric.title(),
            x=df['project_name'],
            y=df[metric],
            marker_color=colors[i]
        ))

    fig2.update_layout(
        title='Issues by Project',
        xaxis_title='Project',
        yaxis_title='Count',
        barmode='group',
        **plot_template
    )
    st.plotly_chart(fig2, use_container_width=True)

    # Quality Metrics Comparison
    st.markdown("### 📈 Coverage and Duplication")
    
    # Create a dual-axis chart for coverage and duplication
    fig3 = go.Figure()
    
    fig3.add_trace(go.Bar(
        name='Coverage',
        x=df['project_name'],
        y=df['coverage'],
        marker_color='#48BB78',
        yaxis='y'
    ))
    
    fig3.add_trace(go.Bar(
        name='Duplication',
        x=df['project_name'],
        y=df['duplicated_lines_density'],
        marker_color='#F56565',
        yaxis='y2'
    ))

    fig3.update_layout(
        title='Coverage and Duplication by Project',
        xaxis_title='Project',
        yaxis_title='Coverage (%)',
        yaxis2=dict(
            title='Duplication (%)',
            overlaying='y',
            side='right',
            gridcolor='#2D3748'
        ),
        barmode='group',
        **plot_template
    )
    st.plotly_chart(fig3, use_container_width=True)

    # Project Rankings
    st.markdown("### 🏆 Project Rankings")
    
    # Create rankings table with size included
    rankings = pd.DataFrame({
        'Project': df['project_name'],
        'Lines of Code': df['ncloc'].apply(format_code_lines),
        'Quality Score': df.apply(lambda row: analyzer.calculate_quality_score(row), axis=1),
        'Total Issues': df['bugs'] + df['vulnerabilities'] + df['code_smells'],
        'Coverage': df['coverage'],
        'Duplication': df['duplicated_lines_density']
    })
    
    rankings = rankings.sort_values('Quality Score', ascending=False)
    rankings = rankings.round(2)
    
    # Display rankings with custom formatting
    st.markdown("""
        <style>
        .dataframe {
            background-color: #1A1F25 !important;
            color: #FAFAFA !important;
        }
        .dataframe th {
            background-color: #2D3748 !important;
            color: #FAFAFA !important;
        }
        .dataframe td {
            background-color: #1A1F25 !important;
            color: #FAFAFA !important;
        }
        </style>
    """, unsafe_allow_html=True)
    
    st.dataframe(rankings.style.format({
        'Quality Score': '{:.1f}',
        'Coverage': '{:.1f}%',
        'Duplication': '{:.1f}%'
    }))
