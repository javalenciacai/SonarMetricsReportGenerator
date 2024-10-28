import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import streamlit as st
from datetime import datetime, timedelta
import numpy as np
from services.metric_analyzer import MetricAnalyzer
from utils.helpers import format_code_lines, format_technical_debt

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
            if len(df) >= period and col in df.columns:
                try:
                    change = ((df[col].iloc[-1] - df[col].iloc[-period]) / df[col].iloc[-period] * 100)
                    changes[f'{col}_{period}d_change'] = change
                except (ZeroDivisionError, TypeError):
                    changes[f'{col}_{period}d_change'] = None
            else:
                changes[f'{col}_{period}d_change'] = None
    return changes

def plot_metrics_history(historical_data):
    """Plot historical metrics data"""
    if not historical_data:
        st.warning("No historical data available")
        return

    try:
        df = pd.DataFrame(historical_data)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df = df.sort_values('timestamp')

        # Ensure numeric types for all metrics
        numeric_columns = ['bugs', 'vulnerabilities', 'code_smells', 'coverage', 
                         'duplicated_lines_density', 'ncloc', 'sqale_index']
        for col in numeric_columns:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')

        # Define metric groups
        issue_metrics = ['bugs', 'vulnerabilities', 'code_smells']
        quality_metrics = ['coverage', 'duplicated_lines_density']
        size_metrics = ['ncloc']
        debt_metrics = ['sqale_index']
        
        # Calculate moving averages
        all_metrics = issue_metrics + quality_metrics + size_metrics + debt_metrics
        available_metrics = [m for m in all_metrics if m in df.columns]
        ma_df = calculate_moving_averages(df, available_metrics)
        
        # Calculate trend changes
        changes = calculate_percentage_changes(df, available_metrics)

        # Dark mode compatible colors
        colors = {
            'bugs': '#F56565',  # Red
            'vulnerabilities': '#ED8936',  # Orange
            'code_smells': '#9F7AEA',  # Purple
            'coverage': '#48BB78',  # Green
            'duplicated_lines_density': '#4299E1',  # Blue
            'ncloc': '#805AD5',  # Purple
            'sqale_index': '#F6AD55'  # Orange
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

        # Project Size Plot
        if 'ncloc' in df.columns:
            fig_size = go.Figure()
            
            # Format ncloc values for hover text
            hover_text = [format_code_lines(val) if pd.notnull(val) else 'N/A' 
                         for val in df['ncloc']]
            
            fig_size.add_trace(go.Scatter(
                x=df['timestamp'],
                y=df['ncloc'],
                name='Lines of Code',
                line=dict(color=colors['ncloc']),
                hovertemplate='Lines of Code: %{text}<br>Date: %{x}',
                text=hover_text
            ))

            if 'ncloc_ma_7d' in ma_df.columns:
                hover_text_ma = [format_code_lines(val) if pd.notnull(val) else 'N/A' 
                               for val in ma_df['ncloc_ma_7d']]
                fig_size.add_trace(go.Scatter(
                    x=df['timestamp'],
                    y=ma_df['ncloc_ma_7d'],
                    name='Lines of Code (7d MA)',
                    line=dict(color=colors['ncloc'], dash='dot'),
                    hovertemplate='7d Moving Average: %{text}<br>Date: %{x}',
                    text=hover_text_ma
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

        # Technical Debt Plot
        if 'sqale_index' in df.columns:
            fig_debt = go.Figure()
            
            hover_text = [format_technical_debt(val) if pd.notnull(val) else 'N/A' 
                         for val in df['sqale_index']]
            
            fig_debt.add_trace(go.Scatter(
                x=df['timestamp'],
                y=df['sqale_index'],
                name='Technical Debt',
                line=dict(color=colors['sqale_index']),
                hovertemplate='Technical Debt: %{text}<br>Date: %{x}',
                text=hover_text
            ))

            if 'sqale_index_ma_7d' in ma_df.columns:
                hover_text_ma = [format_technical_debt(val) if pd.notnull(val) else 'N/A' 
                               for val in ma_df['sqale_index_ma_7d']]
                fig_debt.add_trace(go.Scatter(
                    x=df['timestamp'],
                    y=ma_df['sqale_index_ma_7d'],
                    name='Technical Debt (7d MA)',
                    line=dict(color=colors['sqale_index'], dash='dot'),
                    hovertemplate='7d Moving Average: %{text}<br>Date: %{x}',
                    text=hover_text_ma
                ))

            fig_debt.update_layout(
                title='Technical Debt Trend Analysis',
                xaxis_title='Date',
                yaxis_title='Technical Debt',
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
            st.plotly_chart(fig_debt, use_container_width=True)

        # Issues Plot
        if any(metric in df.columns for metric in issue_metrics):
            fig1 = go.Figure()
            
            for metric in issue_metrics:
                if metric in df.columns:
                    fig1.add_trace(go.Scatter(
                        x=df['timestamp'],
                        y=df[metric],
                        name=metric.replace('_', ' ').title(),
                        line=dict(color=colors[metric])
                    ))
                    if f'{metric}_ma_7d' in ma_df.columns:
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
        if any(metric in df.columns for metric in quality_metrics):
            fig2 = go.Figure()
            
            for metric in quality_metrics:
                if metric in df.columns:
                    fig2.add_trace(go.Scatter(
                        x=df['timestamp'],
                        y=df[metric],
                        name=metric.replace('_', ' ').title(),
                        line=dict(color=colors[metric])
                    ))
                    if f'{metric}_ma_7d' in ma_df.columns:
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
            st.markdown('<p style="color: #FAFAFA;"><strong>Project Metrics (7 days)</strong></p>', unsafe_allow_html=True)
            for metric in ['ncloc', 'sqale_index']:
                if metric in df.columns:
                    change = changes.get(f'{metric}_7d_change')
                    if change is not None:
                        metric_name = 'Lines of Code' if metric == 'ncloc' else 'Technical Debt'
                        emoji = "📈" if change > 0 else "📉" if change < 0 else "➡️"
                        color = "#48BB78" if (metric == 'ncloc' and change > 0) or (metric == 'sqale_index' and change < 0) else "#F56565"
                        st.markdown(
                            f'<p style="color: #FAFAFA;">{metric_name}: '
                            f'<span style="color: {color}">{change:+.1f}% {emoji}</span></p>',
                            unsafe_allow_html=True
                        )

        with col2:
            st.markdown('<p style="color: #FAFAFA;"><strong>Issue Metrics (7 days)</strong></p>', unsafe_allow_html=True)
            for metric in issue_metrics:
                if metric in df.columns:
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
            st.markdown('<p style="color: #FAFAFA;"><strong>Quality Metrics (7 days)</strong></p>', unsafe_allow_html=True)
            for metric in quality_metrics:
                if metric in df.columns:
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

    try:
        # Convert data to DataFrame for easier plotting
        metrics_list = []
        for project_key, data in projects_data.items():
            metrics = data['metrics']
            metrics['project_key'] = project_key
            metrics['project_name'] = data['name']
            metrics_list.append(metrics)
        
        df = pd.DataFrame(metrics_list)

        # Ensure numeric types for metrics
        numeric_columns = ['bugs', 'vulnerabilities', 'code_smells', 'coverage', 
                         'duplicated_lines_density', 'ncloc', 'sqale_index']
        for col in numeric_columns:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')

        # Calculate quality scores
        analyzer = MetricAnalyzer()
        df['quality_score'] = df.apply(lambda row: analyzer.calculate_quality_score(row), axis=1)

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

        # Project Size & Debt Comparison
        st.markdown("### 📏 Project Size & Technical Debt")
        
        if 'ncloc' in df.columns:
            # Size comparison
            fig_size = go.Figure()
            hover_text = [format_code_lines(val) if pd.notnull(val) else 'N/A' 
                         for val in df['ncloc']]
            
            fig_size.add_trace(go.Bar(
                x=df['project_name'],
                y=df['ncloc'],
                name='Lines of Code',
                marker_color='#805AD5',
                text=hover_text,
                hovertemplate='Lines of Code: %{text}<br>Project: %{x}'
            ))
            
            fig_size.update_layout(
                title='Lines of Code by Project',
                xaxis_title='Project',
                yaxis_title='Lines of Code',
                **plot_template
            )
            st.plotly_chart(fig_size, use_container_width=True)

        if 'sqale_index' in df.columns:
            # Technical Debt comparison
            fig_debt = go.Figure()
            hover_text = [format_technical_debt(val) if pd.notnull(val) else 'N/A' 
                         for val in df['sqale_index']]
            
            fig_debt.add_trace(go.Bar(
                x=df['project_name'],
                y=df['sqale_index'],
                name='Technical Debt',
                marker_color='#F6AD55',
                text=hover_text,
                hovertemplate='Technical Debt: %{text}<br>Project: %{x}'
            ))
            
            fig_debt.update_layout(
                title='Technical Debt by Project',
                xaxis_title='Project',
                yaxis_title='Technical Debt',
                **plot_template
            )
            st.plotly_chart(fig_debt, use_container_width=True)

        # Quality Score Bar Chart
        st.markdown("### 📊 Quality Metrics Comparison")
        
        fig1 = go.Figure()
        fig1.add_trace(go.Bar(
            x=df['project_name'],
            y=df['quality_score'],
            name='Quality Score',
            marker_color='#48BB78',
            text=df['quality_score'].round(1),
            textposition='auto',
            hovertemplate='Quality Score: %{text}<br>Project: %{x}'
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
        available_metrics = [m for m in issue_metrics if m in df.columns]
        
        if available_metrics:
            fig2 = go.Figure()
            
            for i, metric in enumerate(available_metrics):
                fig2.add_trace(go.Bar(
                    name=metric.title(),
                    x=df['project_name'],
                    y=df[metric],
                    marker_color=colors[i],
                    text=df[metric].round(0),
                    textposition='auto',
                    hovertemplate='%{text}<br>Project: %{x}'
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
        
        quality_metrics = ['coverage', 'duplicated_lines_density']
        available_metrics = [m for m in quality_metrics if m in df.columns]
        
        if available_metrics:
            fig3 = go.Figure()
            
            for i, metric in enumerate(available_metrics):
                fig3.add_trace(go.Bar(
                    name=metric.replace('_', ' ').title(),
                    x=df['project_name'],
                    y=df[metric],
                    marker_color=colors[i],
                    text=df[metric].round(1),
                    textposition='auto',
                    hovertemplate='%{text}%<br>Project: %{x}'
                ))

            fig3.update_layout(
                title='Coverage and Duplication by Project',
                xaxis_title='Project',
                yaxis_title='Percentage',
                barmode='group',
                **plot_template
            )
            st.plotly_chart(fig3, use_container_width=True)

        # Project Rankings
        st.markdown("### 🏆 Project Rankings")
        
        # Create rankings table
        rankings = pd.DataFrame({
            'Project': df['project_name'],
            'Lines of Code': df['ncloc'].apply(lambda x: format_code_lines(x) if pd.notnull(x) else 'N/A'),
            'Technical Debt': df['sqale_index'].apply(lambda x: format_technical_debt(x) if pd.notnull(x) else 'N/A'),
            'Quality Score': df['quality_score'].round(1),
            'Total Issues': df[issue_metrics].sum(axis=1).round(0) if all(m in df.columns for m in issue_metrics) else None,
            'Coverage': df['coverage'].round(1) if 'coverage' in df.columns else None,
            'Duplication': df['duplicated_lines_density'].round(1) if 'duplicated_lines_density' in df.columns else None
        })
        
        rankings = rankings.sort_values('Quality Score', ascending=False)
        
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
        
        st.dataframe(rankings)

    except Exception as e:
        st.error(f"Error creating multi-project comparison: {str(e)}")
