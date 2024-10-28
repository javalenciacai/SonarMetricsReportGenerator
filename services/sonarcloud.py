import requests
import streamlit as st
from config import SONARCLOUD_API_URL
import json

class SonarCloudAPI:
    def __init__(self, token):
        self.token = token
        self.headers = {
            'Authorization': f'Bearer {token}',
            'Accept': 'application/json'
        }
        self.organization = None
        self.api_version = None

    def _check_api_version(self):
        """Check SonarCloud API version compatibility"""
        try:
            response = requests.get(
                f"{SONARCLOUD_API_URL}/server/version",
                headers=self.headers
            )
            response.raise_for_status()
            self.api_version = response.text.strip()
            return True
        except requests.exceptions.RequestException as e:
            st.error(f"Error checking API version: {str(e)}")
            return False

    def validate_token(self):
        """Validate the SonarCloud token by making a test API call"""
        if not self._check_api_version():
            return False, "Could not verify API version compatibility"

        try:
            response = requests.get(
                f"{SONARCLOUD_API_URL}/organizations/search",
                headers=self.headers,
                params={'member': 'true'}  # Only show organizations where the user is member
            )
            
            if response.status_code == 401:
                return False, "Invalid token. Please check your SonarCloud token."
            
            response.raise_for_status()
            orgs = response.json().get('organizations', [])
            
            if not orgs:
                return False, "No organizations found for this token"
            
            # Set the first organization as default
            self.organization = orgs[0]['key']
            return True, f"Token validated successfully. API Version: {self.api_version}"
            
        except requests.exceptions.RequestException as e:
            return False, f"Error validating token: {str(e)}"

    def get_projects(self):
        """Get all projects for the current organization"""
        if not self.organization:
            st.error("Organization not set. Please validate your token first.")
            return []
        
        try:
            # Initialize parameters with required fields
            params = {
                'organization': self.organization,
                'ps': 100,  # Number of projects per page
                'analyzed': 'true',  # Only return analyzed projects
                'onProvisionedOnly': 'false',  # Include all projects
                'projects': '',  # Empty string to return all projects
                'filter': 'analyzedBefore'  # Sort by last analysis date
            }
            
            response = requests.get(
                f"{SONARCLOUD_API_URL}/projects/search",
                headers=self.headers,
                params=params
            )
            
            response.raise_for_status()
            return response.json()['components']
            
        except requests.exceptions.RequestException as e:
            st.error(f"Error fetching projects: {str(e)}")
            return []
        except (KeyError, json.JSONDecodeError) as e:
            st.error(f"Error parsing project data: {str(e)}")
            return []

    def get_project_metrics(self, project_key):
        """Get metrics for a specific project"""
        if not self.organization:
            st.error("Organization not set. Please validate your token first.")
            return []

        # Define the metrics we want to retrieve
        metrics = [
            'bugs',
            'vulnerabilities',
            'code_smells',
            'coverage',
            'duplicated_lines_density',
            'ncloc',  # Additional metric for lines of code
            'reliability_rating',
            'security_rating',
            'sqale_rating'  # Maintainability rating
        ]
        
        try:
            response = requests.get(
                f"{SONARCLOUD_API_URL}/measures/component",
                headers=self.headers,
                params={
                    'component': project_key,
                    'metricKeys': ','.join(metrics),
                    'organization': self.organization,
                    'additionalFields': 'metrics,periods'  # Get additional metric information
                }
            )
            
            response.raise_for_status()
            component_data = response.json().get('component', {})
            
            if not component_data:
                st.error(f"No data found for project {project_key}")
                return []
                
            return component_data.get('measures', [])
            
        except requests.exceptions.RequestException as e:
            st.error(f"Error fetching metrics: {str(e)}")
            return []
        except (KeyError, json.JSONDecodeError) as e:
            st.error(f"Error parsing metric data: {str(e)}")
            return []

    def get_project_branches(self, project_key):
        """Get all branches for a specific project"""
        try:
            response = requests.get(
                f"{SONARCLOUD_API_URL}/project_branches/list",
                headers=self.headers,
                params={
                    'project': project_key,
                    'organization': self.organization
                }
            )
            
            response.raise_for_status()
            return response.json().get('branches', [])
            
        except requests.exceptions.RequestException as e:
            st.error(f"Error fetching project branches: {str(e)}")
            return []
