import streamlit as st
import pandas as pd

def display_current_metrics(metrics_data):
    st.subheader("Current Metrics")
    
    cols = st.columns(5)
    with cols[0]:
        st.metric("Bugs", metrics_data.get('bugs', 0))
    with cols[1]:
        st.metric("Vulnerabilities", metrics_data.get('vulnerabilities', 0))
    with cols[2]:
        st.metric("Code Smells", metrics_data.get('code_smells', 0))
    with cols[3]:
        st.metric("Coverage", f"{metrics_data.get('coverage', 0)}%")
    with cols[4]:
        st.metric("Duplicated Lines", f"{metrics_data.get('duplicated_lines_density', 0)}%")

def create_download_report(data):
    df = pd.DataFrame(data)
    csv = df.to_csv(index=False)
    st.download_button(
        label="Download CSV Report",
        data=csv,
        file_name="sonarcloud_metrics.csv",
        mime="text/csv"
    )
