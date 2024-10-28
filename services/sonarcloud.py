import requests
import streamlit as st
from config import SONARCLOUD_API_URL

class SonarCloudAPI:
    def __init__(self, token):
        self.token = token
        self.headers = {
            'Authorization': f'Bearer {token}'
        }
        self.organization = None

    def validate_token(self):
        """Validate the SonarCloud token by making a test API call"""
        try:
            response = requests.get(
                f"{SONARCLOUD_API_URL}/organizations/search",
                headers=self.headers
            )
            if response.status_code == 401:
                return False, "Invalid token. Please check your SonarCloud token."
            response.raise_for_status()
            orgs = response.json().get('organizations', [])
            if orgs:
                self.organization = orgs[0]['key']  # Set the first organization as default
                return True, "Token validated successfully"
            return False, "No organizations found for this token"
        except requests.exceptions.RequestException as e:
            return False, f"Error validating token: {str(e)}"

    def get_projects(self):
        if not self.organization:
            st.error("Organization not set. Please validate your token first.")
            return []
        
        try:
            response = requests.get(
                f"{SONARCLOUD_API_URL}/projects/search",
                headers=self.headers,
                params={
                    'organization': self.organization,
                    'ps': 100  # Number of projects per page
                }
            )
            response.raise_for_status()
            return response.json()['components']
        except Exception as e:
            st.error(f"Error fetching projects: {str(e)}")
            return []

    def get_project_metrics(self, project_key):
        if not self.organization:
            st.error("Organization not set. Please validate your token first.")
            return []

        metrics = "bugs,vulnerabilities,code_smells,coverage,duplicated_lines_density"
        try:
            response = requests.get(
                f"{SONARCLOUD_API_URL}/measures/component",
                headers=self.headers,
                params={
                    'component': project_key,
                    'metricKeys': metrics,
                    'organization': self.organization
                }
            )
            response.raise_for_status()
            return response.json()['component']['measures']
        except Exception as e:
            st.error(f"Error fetching metrics: {str(e)}")
            return []
