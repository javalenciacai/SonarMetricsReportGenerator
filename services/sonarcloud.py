import requests
import streamlit as st
from config import SONARCLOUD_API_URL

class SonarCloudAPI:
    def __init__(self, token):
        self.token = token
        self.headers = {
            'Authorization': f'Bearer {token}'
        }

    def get_projects(self):
        try:
            response = requests.get(
                f"{SONARCLOUD_API_URL}/projects/search",
                headers=self.headers
            )
            response.raise_for_status()
            return response.json()['components']
        except Exception as e:
            st.error(f"Error fetching projects: {str(e)}")
            return []

    def get_project_metrics(self, project_key):
        metrics = "bugs,vulnerabilities,code_smells,coverage,duplicated_lines_density"
        try:
            response = requests.get(
                f"{SONARCLOUD_API_URL}/measures/component",
                headers=self.headers,
                params={
                    'component': project_key,
                    'metricKeys': metrics
                }
            )
            response.raise_for_status()
            return response.json()['component']['measures']
        except Exception as e:
            st.error(f"Error fetching metrics: {str(e)}")
            return []
