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
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)

    def _log_request(self, method, url, params=None, response=None):
        """Log API request details for debugging"""
        if self.debug_mode:
            self.logger.debug(f"API Request: {method} {url}")
            self.logger.debug(f"Parameters: {params}")
            if response:
                self.logger.debug(f"Status Code: {response.status_code}")
                try:
                    self.logger.debug(f"Response: {response.json()}")
                except:
                    if hasattr(response, 'text'):
                        self.logger.debug(f"Raw Response: {response.text}")
                    else:
                        self.logger.debug("No response content available")

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
                self.logger.error(f"{error_msg}\nAPI Response: {e.response.text}")
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
            return True, "Token validated successfully."
            
        except requests.exceptions.RequestException as e:
            error_message = "Failed to validate token. Please check your connection and try again."
            self.logger.error(f"Token validation error: {str(e)}")
            if hasattr(e, 'response') and hasattr(e.response, 'text'):
                self.logger.error(f"API Response: {e.response.text}")
            return False, error_message

    def get_projects(self):
        """Get all projects for the current organization"""
        if not self.organization:
            st.error("Organization not set. Please validate your token first.")
            return []
        
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
                error_msg = "Unexpected API response format"
                self.logger.error(f"{error_msg}: {data}")
                return []
                
            return data['components']
            
        except requests.exceptions.RequestException as e:
            error_message = "Failed to fetch projects"
            self.logger.error(f"{error_message}: {str(e)}")
            if hasattr(e, 'response') and hasattr(e.response, 'text'):
                self.logger.error(f"API Response: {e.response.text}")
            st.error(error_message)
            return []
        except (KeyError, json.JSONDecodeError) as e:
            error_msg = "Error parsing project data"
            self.logger.error(f"{error_msg}: {str(e)}")
            st.error(error_msg)
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
                self.logger.error(error_msg)
                return []
                
            return component_data.get('measures', [])
            
        except requests.exceptions.RequestException as e:
            error_message = "Failed to fetch metrics"
            self.logger.error(f"{error_message}: {str(e)}")
            if hasattr(e, 'response') and hasattr(e.response, 'text'):
                self.logger.error(f"API Response: {e.response.text}")
            st.error(error_message)
            return []
        except (KeyError, json.JSONDecodeError) as e:
            error_msg = "Error parsing metric data"
            self.logger.error(f"{error_msg}: {str(e)}")
            st.error(error_msg)
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
            error_message = "Failed to fetch project branches"
            self.logger.error(f"{error_message}: {str(e)}")
            if hasattr(e, 'response') and hasattr(e.response, 'text'):
                self.logger.error(f"API Response: {e.response.text}")
            st.error(error_message)
            return []
