import requests
import streamlit as st
from config import SONARCLOUD_API_URL
import json
import logging

class SonarCloudAPI:
    def __init__(self, token):
        self.token = token
        self.headers = {
            'Authorization': f'Bearer {token}',
            'Accept': 'application/json'
        }
        self.organization = None
        self.api_version = None
        self.debug_mode = True  # Enable debug mode for troubleshooting

    def _log_request(self, method, url, params=None, response=None):
        """Log API request details for debugging"""
        if self.debug_mode:
            st.write("Debug Information:")
            st.write(f"API Request: {method} {url}")
            st.write(f"Parameters: {params}")
            if response:
                st.write(f"Status Code: {response.status_code}")
                try:
                    st.write(f"Response: {response.json()}")
                except:
                    if hasattr(response, 'text'):
                        st.write(f"Raw Response: {response.text}")
                    else:
                        st.write("No response content available")

    def _check_api_version(self):
        """Check SonarCloud API version compatibility"""
        url = f"{SONARCLOUD_API_URL}/server/version"
        try:
            response = requests.get(url, headers=self.headers)
            self._log_request("GET", url, response=response)
            response.raise_for_status()
            self.api_version = response.text.strip()
            return True
        except requests.exceptions.RequestException as e:
            error_msg = f"Error checking API version: {str(e)}"
            if hasattr(e, 'response') and hasattr(e.response, 'text'):
                error_msg += f"\nAPI Response: {e.response.text}"
            st.error(error_msg)
            return False

    def validate_token(self):
        """Validate the SonarCloud token by making a test API call"""
        if not self._check_api_version():
            return False, "Could not verify API version compatibility"

        url = f"{SONARCLOUD_API_URL}/organizations/search"
        params = {'member': 'true'}
        
        try:
            response = requests.get(url, headers=self.headers, params=params)
            self._log_request("GET", url, params, response)
            
            if response.status_code == 401:
                return False, "Invalid token. Please check your SonarCloud token."
            
            response.raise_for_status()
            orgs = response.json().get('organizations', [])
            
            if not orgs:
                return False, "No organizations found for this token"
            
            self.organization = orgs[0]['key']
            return True, f"Token validated successfully. API Version: {self.api_version}"
            
        except requests.exceptions.RequestException as e:
            error_message = str(e)
            if hasattr(e, 'response') and hasattr(e.response, 'text'):
                error_message += f"\nAPI Response: {e.response.text}"
            st.error(f"Error validating token: {error_message}")
            return False, error_message

    def get_projects(self):
        """Get all projects for the current organization"""
        if not self.organization:
            st.error("Organization not set. Please validate your token first.")
            return []
        
        # Fixed URL by removing duplicate 'api'
        url = f"{SONARCLOUD_API_URL}/projects/search"
        params = {
            'organization': self.organization,
            'ps': 100,  # Number of projects per page
            'analyzed': 'true'  # Only return analyzed projects
        }
        
        try:
            response = requests.get(url, headers=self.headers, params=params)
            self._log_request("GET", url, params, response)
            
            response.raise_for_status()
            data = response.json()
            
            if 'components' not in data:
                error_msg = f"Unexpected API response format: {data}"
                st.error(error_msg)
                self.logger.error(error_msg)
                return []
                
            return data['components']
            
        except requests.exceptions.RequestException as e:
            error_message = str(e)
            if hasattr(e, 'response') and hasattr(e.response, 'text'):
                error_message += f"\nAPI Response: {e.response.text}"
            st.error(f"Error fetching projects: {error_message}")
            return []
        except (KeyError, json.JSONDecodeError) as e:
            error_msg = f"Error parsing project data: {str(e)}"
            st.error(error_msg)
            self.logger.error(error_msg)
            return []

    def get_project_metrics(self, project_key):
        """Get metrics for a specific project"""
        if not self.organization:
            st.error("Organization not set. Please validate your token first.")
            return []

        metrics = [
            'bugs',
            'vulnerabilities',
            'code_smells',
            'coverage',
            'duplicated_lines_density',
            'ncloc',
            'reliability_rating',
            'security_rating',
            'sqale_rating'
        ]
        
        url = f"{SONARCLOUD_API_URL}/measures/component"
        params = {
            'component': project_key,
            'metricKeys': ','.join(metrics),
            'organization': self.organization,
            'additionalFields': 'metrics,periods'
        }
        
        try:
            response = requests.get(url, headers=self.headers, params=params)
            self._log_request("GET", url, params, response)
            
            response.raise_for_status()
            component_data = response.json().get('component', {})
            
            if not component_data:
                error_msg = f"No data found for project {project_key}"
                st.error(error_msg)
                self.logger.error(error_msg)
                return []
                
            return component_data.get('measures', [])
            
        except requests.exceptions.RequestException as e:
            error_message = str(e)
            if hasattr(e, 'response') and hasattr(e.response, 'text'):
                error_message += f"\nAPI Response: {e.response.text}"
            st.error(f"Error fetching metrics: {error_message}")
            return []
        except (KeyError, json.JSONDecodeError) as e:
            error_msg = f"Error parsing metric data: {str(e)}"
            st.error(error_msg)
            self.logger.error(error_msg)
            return []

    def get_project_branches(self, project_key):
        """Get all branches for a specific project"""
        url = f"{SONARCLOUD_API_URL}/project_branches/list"
        params = {
            'project': project_key,
            'organization': self.organization
        }
        
        try:
            response = requests.get(url, headers=self.headers, params=params)
            self._log_request("GET", url, params, response)
            
            response.raise_for_status()
            return response.json().get('branches', [])
            
        except requests.exceptions.RequestException as e:
            error_message = str(e)
            if hasattr(e, 'response') and hasattr(e.response, 'text'):
                error_message += f"\nAPI Response: {e.response.text}"
            st.error(f"Error fetching project branches: {error_message}")
            return []
