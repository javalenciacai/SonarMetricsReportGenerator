import streamlit as st
import pandas as pd
from services.metric_analyzer import MetricAnalyzer
from utils.helpers import format_code_lines, format_technical_debt
from database.schema import get_update_preferences
from database.connection import execute_query
from datetime import datetime, timezone
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from services.metrics_processor import MetricsProcessor

def calculate_metric_trends(metrics_processor, project_key, metric_name, days=7):
    """Calculate trend for a specific metric"""
    historical_data = metrics_processor.get_historical_data(project_key)
    if not historical_data:
        return None, None
    
    df = pd.DataFrame(historical_data)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df = df.sort_values('timestamp')
    
    if len(df) < 2:
        return None, None
    
    current_value = float(df[metric_name].iloc[-1])
    previous_value = float(df[metric_name].iloc[0])
    change = ((current_value - previous_value) / previous_value * 100) if previous_value != 0 else 0
    
    return current_value, change

def plot_all_projects_trends(projects_data, metrics_processor):
    """Create trend visualization for all projects"""
    if not projects_data:
        return
    
    metrics_to_plot = ['bugs', 'vulnerabilities', 'code_smells', 'coverage']
    metric_names = {
        'bugs': 'Bugs 🐛',
        'vulnerabilities': 'Vulnerabilities ⚠️',
        'code_smells': 'Code Smells 🔧',
        'coverage': 'Coverage 📊'
    }
    
    # Create figure with subplots
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=[metric_names[m] for m in metrics_to_plot],
        vertical_spacing=0.15,
        horizontal_spacing=0.1
    )
    
    # Colors for different trends
    colors = {
        'positive': '#48BB78',  # green
        'negative': '#F56565',  # red
        'neutral': '#A0AEC0'    # gray
    }
    
    for idx, metric in enumerate(metrics_to_plot):
        row = (idx // 2) + 1
        col = (idx % 2) + 1
        
        data = []
        for project_key, project_info in projects_data.items():
            try:
                current_value, change = calculate_metric_trends(
                    metrics_processor, 
                    project_key, 
                    metric
                )
                
                if current_value is not None:
                    color = colors['neutral']
                    if metric in ['coverage']:
                        color = colors['positive'] if change > 0 else colors['negative'] if change < 0 else colors['neutral']
                    else:
                        color = colors['positive'] if change < 0 else colors['negative'] if change > 0 else colors['neutral']
                    
                    data.append({
                        'name': project_info['name'],
                        'value': current_value,
                        'change': change,
                        'color': color
                    })
            except Exception as e:
                st.warning(f"Could not calculate trends for {project_info['name']}: {str(e)}")
        
        if data:
            # Sort by absolute change
            data.sort(key=lambda x: abs(x['change']), reverse=True)
            
            fig.add_trace(
                go.Bar(
                    name=metric_names[metric],
                    x=[d['name'] for d in data],
                    y=[d['change'] for d in data],
                    marker_color=[d['color'] for d in data],
                    text=[f"{d['change']:.1f}%" for d in data],
                    textposition='auto',
                    showlegend=False
                ),
                row=row, col=col
            )
            
            fig.update_xaxes(tickangle=45, row=row, col=col)
            fig.update_yaxes(title_text='% Change', row=row, col=col)
    
    fig.update_layout(
        height=800,
        title_text="Metric Trends (7-day Change)",
        title_x=0.5,
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#FAFAFA'),
        showlegend=False
    )
    
    st.plotly_chart(fig, use_container_width=True)

def display_multi_project_metrics(projects_data, metrics_processor=None):
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
    if metrics_processor is None:
        metrics_processor = MetricsProcessor()
    
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
    for project_key, data in projects_data.items():
        metrics = data['metrics']
        metrics['project_key'] = project_key
        metrics['project_name'] = data['name']
        metrics['is_active'] = data.get('is_active', True)
        metrics['quality_score'] = analyzer.calculate_quality_score(metrics)
        
        # Add to totals
        for metric in total_metrics.keys():
            if metric in metrics:
                total_metrics[metric] += float(metrics[metric])
        
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
    
    # Add trend visualization
    st.markdown("### 📈 Metric Trends")
    st.markdown("""
        <p style='color: #A0AEC0;'>
        Showing 7-day metric changes across all projects. 
        Green indicates improvement, red indicates degradation.
        </p>
    """, unsafe_allow_html=True)
    
    plot_all_projects_trends(projects_data, metrics_processor)
    
    # Sort projects by quality score
    df = pd.DataFrame(metrics_list)
    df = df.sort_values('quality_score', ascending=False)
    
    # Display individual project cards
    for _, row in df.iterrows():
        st.markdown(f"""
            <div class="project-card">
                <h3 style="color: #FAFAFA;">
                    {row['project_name']}
                    <span style="float: right; font-size: 0.8em; padding: 0.25em 0.5em; background: #2D3748; border-radius: 0.25em;">
                        {row['quality_score']:.1f}/100
                    </span>
                </h3>
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
        <div class="metric-grid">
            <div class="metric-item">
                <div class="metric-title">Lines of Code</div>
                <div class="metric-value">{ncloc} 📏</div>
            </div>
            <div class="metric-item">
                <div class="metric-title">Technical Debt</div>
                <div class="metric-value">{sqale_index} ⏱️</div>
            </div>
            <div class="metric-item">
                <div class="metric-title">Bugs</div>
                <div class="metric-value">{bugs} 🐛</div>
            </div>
            <div class="metric-item">
                <div class="metric-title">Vulnerabilities</div>
                <div class="metric-value">{vulnerabilities} ⚠️</div>
            </div>
            <div class="metric-item">
                <div class="metric-title">Code Smells</div>
                <div class="metric-value">{code_smells} 🔧</div>
            </div>
            <div class="metric-item">
                <div class="metric-title">Coverage</div>
                <div class="metric-value">{coverage}% 📊</div>
            </div>
            <div class="metric-item">
                <div class="metric-title">Duplication</div>
                <div class="metric-value">{duplicated_lines_density}% 📝</div>
            </div>
        </div>
    """.format(**metrics_data), unsafe_allow_html=True)

def create_download_report(projects_data):
    """Create downloadable CSV report"""
    df = pd.DataFrame([
        {
            'Project': data['name'],
            'Lines of Code': data['metrics'].get('ncloc', 0),
            'Bugs': data['metrics'].get('bugs', 0),
            'Vulnerabilities': data['metrics'].get('vulnerabilities', 0),
            'Code Smells': data['metrics'].get('code_smells', 0),
            'Coverage (%)': data['metrics'].get('coverage', 0),
            'Duplication (%)': data['metrics'].get('duplicated_lines_density', 0),
            'Technical Debt (days)': data['metrics'].get('sqale_index', 0) / (8 * 60) if 'sqale_index' in data['metrics'] else 0
        }
        for project_key, data in projects_data.items()
    ])
    
    csv = df.to_csv(index=False)
    st.download_button(
        label="📥 Download Report",
        data=csv,
        file_name=f"sonar_metrics_report_{datetime.now(timezone.utc).strftime('%Y%m%d')}.csv",
        mime="text/csv"
    )

def display_metric_trends(historical_data):
    """Display metric trends over time"""
    if not historical_data:
        st.warning("No historical data available for trend analysis")
        return
    
    df = pd.DataFrame(historical_data)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df = df.sort_values('timestamp')
    
    # Calculate changes
    latest = df.iloc[-1]
    oldest = df.iloc[0]
    
    metrics = {
        'bugs': ('Bugs', '🐛'),
        'vulnerabilities': ('Vulnerabilities', '⚠️'),
        'code_smells': ('Code Smells', '🔧'),
        'coverage': ('Coverage', '📊'),
    }
    
    st.markdown("### 📈 Metric Trends")
    
    for metric, (label, emoji) in metrics.items():
        current = float(latest[metric])
        previous = float(oldest[metric])
        change = ((current - previous) / previous * 100) if previous != 0 else 0
        
        # Determine trend direction
        if metric == 'coverage':
            trend = '📈' if change > 0 else '📉' if change < 0 else '➡️'
            color = 'green' if change > 0 else 'red' if change < 0 else 'gray'
        else:
            trend = '📈' if change < 0 else '📉' if change > 0 else '➡️'
            color = 'green' if change < 0 else 'red' if change > 0 else 'gray'
        
        st.markdown(f"""
            <div style="margin-bottom: 1rem;">
                <span style="font-size: 1.1rem;">{label} {emoji}</span><br>
                <span style="color: {color};">
                    {trend} {abs(change):.1f}% {'decrease' if change < 0 else 'increase' if change > 0 else 'no change'}
                </span>
            </div>
        """, unsafe_allow_html=True)
