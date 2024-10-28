import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import streamlit as st
from datetime import datetime, timedelta
import numpy as np

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
    if not historical_data:
        st.warning("No historical data available")
        return

    df = pd.DataFrame(historical_data)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df = df.sort_values('timestamp')

    # Define metric groups
    issue_metrics = ['bugs', 'vulnerabilities', 'code_smells']
    quality_metrics = ['coverage', 'duplicated_lines_density']
    
    try:
        # Calculate moving averages
        ma_df = calculate_moving_averages(df, issue_metrics + quality_metrics)
        
        # Calculate trend changes
        changes = calculate_percentage_changes(df, issue_metrics + quality_metrics)

        # Dark mode compatible colors
        colors = {
            'bugs': '#F56565',  # Red
            'vulnerabilities': '#ED8936',  # Orange
            'code_smells': '#9F7AEA',  # Purple
            'coverage': '#48BB78',  # Green
            'duplicated_lines_density': '#4299E1'  # Blue
        }

        # Plot template for dark mode
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

        # Issues Plot
        fig1 = go.Figure()
        
        # Add traces for each issue metric
        for metric in issue_metrics:
            fig1.add_trace(go.Scatter(
                x=df['timestamp'],
                y=df[metric],
                name=metric.replace('_', ' ').title(),
                line=dict(color=colors[metric])
            ))
            # Add moving averages
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
            # Add moving averages
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

        # Display trend summary with dark mode compatible colors
        st.markdown('<h3 style="color: #FAFAFA;">Trend Summary</h3>', unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        
        with col1:
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

        with col2:
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

        # Display 30-day trend analysis
        st.markdown('<h3 style="color: #FAFAFA;">30-Day Trend Analysis</h3>', unsafe_allow_html=True)
        col3, col4 = st.columns(2)
        
        with col3:
            st.markdown('<p style="color: #FAFAFA;"><strong>Issue Metrics Changes (30 days)</strong></p>', unsafe_allow_html=True)
            for metric in issue_metrics:
                change = changes.get(f'{metric}_30d_change')
                if change is not None:
                    emoji = "📉" if change < 0 else "📈" if change > 0 else "➡️"
                    color = "#48BB78" if change < 0 else "#F56565" if change > 0 else "#A0AEC0"
                    st.markdown(
                        f'<p style="color: #FAFAFA;">{metric.replace("_", " ").title()}: '
                        f'<span style="color: {color}">{change:+.1f}% {emoji}</span></p>',
                        unsafe_allow_html=True
                    )

        with col4:
            st.markdown('<p style="color: #FAFAFA;"><strong>Quality Metrics Changes (30 days)</strong></p>', unsafe_allow_html=True)
            for metric in quality_metrics:
                change = changes.get(f'{metric}_30d_change')
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
