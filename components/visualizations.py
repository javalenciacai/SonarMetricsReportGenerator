import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import streamlit as st

def plot_metrics_history(historical_data):
    if not historical_data:
        st.warning("No historical data available")
        return

    df = pd.DataFrame(historical_data)
    
    # Time series plot for bugs, vulnerabilities, and code smells
    fig1 = go.Figure()
    fig1.add_trace(go.Scatter(x=df['timestamp'], y=df['bugs'], name='Bugs'))
    fig1.add_trace(go.Scatter(x=df['timestamp'], y=df['vulnerabilities'], name='Vulnerabilities'))
    fig1.add_trace(go.Scatter(x=df['timestamp'], y=df['code_smells'], name='Code Smells'))
    fig1.update_layout(title='Issues Over Time', xaxis_title='Date', yaxis_title='Count')
    st.plotly_chart(fig1)

    # Coverage trend
    fig2 = px.line(df, x='timestamp', y='coverage', title='Code Coverage Trend')
    st.plotly_chart(fig2)
