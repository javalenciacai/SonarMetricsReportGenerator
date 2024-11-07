import requests
import json
import logging
from config import SONARCLOUD_API_URL
import streamlit as st
import time
from typing import Tuple, Optional, Dict, List, Any

class SonarCloudAPI:
    def __init__(self, token: str):
        self.token = token
        self.headers = {
            'Authorization': f'Bearer {token}',
            'Accept': 'application/json'
        }
        self.organization = None
        self.api_version = None
        self.debug_mode = True
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        self.max_retries = 3
        self.retry_delay = 2  # seconds

    def _log_request(self, method: str, url: str, params: Optional[Dict] = None, response: Optional[requests.Response] = None) -> None:
        """Log API request details for debugging"""
        if self.debug_mode:
            self.logger.debug(f"API Request: {method} {url}")
            self.logger.debug(f"Parameters: {params}")
            if response:
                self.logger.debug(f"Status Code: {response.status_code}")
                try:
                    response_data = response.json() if response.content else "No content"
                    self.logger.debug(f"Response: {json.dumps(response_data, indent=2)}")
                except json.JSONDecodeError:
                    self.logger.debug(f"Raw Response: {response.text}")
                except Exception as e:
                    self.logger.debug(f"Error parsing response: {str(e)}")

    def _validate_response(self, response: requests.Response, expected_keys: Optional[List[str]] = None) -> Tuple[bool, Any]:
        """Validate API response format and content"""
        try:
            if not response.content:
                return False, "Empty response from API"
            
            data = response.json()
            if expected_keys:
                missing_keys = [key for key in expected_keys if key not in data]
                if missing_keys:
                    return False, f"Missing expected keys in response: {missing_keys}"
            
            return True, data
        except json.JSONDecodeError:
            return False, f"Invalid JSON response: {response.text}"
        except Exception as e:
            return False, f"Error validating response: {str(e)}"

    def _make_request_with_retry(self, method: str, url: str, params: Optional[Dict] = None) -> Tuple[bool, Any]:
        """Make API request with retry mechanism"""
        for attempt in range(self.max_retries):
            try:
                response = requests.get(url, headers=self.headers, params=params)
                self._log_request(method, url, params, response)

                if response.status_code == 401:
                    return False, "Invalid token. Please check your SonarCloud token."
                elif response.status_code == 403:
                    return False, "Insufficient permissions. Please check your token permissions."
                elif response.status_code == 404:
                    return False, "Resource not found. Please check your request parameters."
                
                response.raise_for_status()
                return True, response
            except requests.exceptions.RequestException as e:
                if attempt < self.max_retries - 1:
                    self.logger.warning(f"Request failed (attempt {attempt + 1}/{self.max_retries}): {str(e)}")
                    time.sleep(self.retry_delay * (attempt + 1))  # Exponential backoff
                    continue
                return False, f"Request failed after {self.max_retries} attempts: {str(e)}"
        
        return False, f"Request failed after {self.max_retries} attempts"

    def _initialize_organization(self) -> Tuple[bool, str]:
        """Initialize organization from user's organizations with retry mechanism"""
        url = f"{SONARCLOUD_API_URL}/organizations/search"
        params = {'member': 'true'}
        
        success, result = self._make_request_with_retry("GET", url, params)
        if not success:
            return False, result
        
        response = result
        is_valid, data = self._validate_response(response, ['organizations'])
        
        if not is_valid:
            return False, data
        
        orgs = data.get('organizations', [])
        if not orgs:
            return False, "No organizations found for this token. Please ensure you have access to at least one organization."
        
        # Store organization in session state and instance
        self.organization = orgs[0]['key']
        if 'sonar_organization' not in st.session_state:
            st.session_state.sonar_organization = self.organization

        self.logger.info(f"Organization initialized: {self.organization}")
        return True, f"Organization initialized: {self.organization}"

    def _check_api_version(self) -> Tuple[bool, str]:
        """Check SonarCloud API version compatibility"""
        url = f"{SONARCLOUD_API_URL}/server/version"
        success, result = self._make_request_with_retry("GET", url)
        
        if not success:
            return False, result
        
        response = result
        self.api_version = response.text.strip()
        self.logger.info(f"API version detected: {self.api_version}")
        return True, f"API version: {self.api_version}"

    def _ensure_organization(self) -> Tuple[bool, str]:
        """Ensure organization is initialized or re-initialize if needed"""
        if not self.organization:
            if 'sonar_organization' in st.session_state:
                self.organization = st.session_state.sonar_organization
                return True, f"Organization restored from session: {self.organization}"
            
            self.logger.info("Organization not initialized, attempting initialization")
            return self._initialize_organization()
        return True, f"Using organization: {self.organization}"

    def validate_token(self) -> Tuple[bool, str]:
        """Validate the SonarCloud token and initialize organization"""
        self.logger.info("Starting token validation process")
        
        # First check API version
        version_valid, version_msg = self._check_api_version()
        if not version_valid:
            self.logger.error(f"API version check failed: {version_msg}")
            return False, version_msg

        # Then initialize organization
        org_valid, org_msg = self._initialize_organization()
        if not org_valid:
            self.logger.error(f"Organization initialization failed: {org_msg}")
            return False, org_msg

        self.logger.info(f"Token validated successfully. Organization: {self.organization}")
        return True, f"Token validated successfully. Using organization: {self.organization}"

    def get_projects(self) -> List[Dict]:
        """Get all projects for the current organization"""
        # Ensure organization is set
        org_valid, org_msg = self._ensure_organization()
        if not org_valid:
            self.logger.error(org_msg)
            return []
        
        url = f"{SONARCLOUD_API_URL}/projects/search"
        params = {
            'organization': self.organization,
            'ps': 100,
            'analyzed': 'true'
        }
        
        success, result = self._make_request_with_retry("GET", url, params)
        if not success:
            self.logger.error(f"Failed to fetch projects: {result}")
            return []
        
        response = result
        is_valid, data = self._validate_response(response, ['components'])
        
        if not is_valid:
            self.logger.error(f"Invalid API response: {data}")
            return []
        
        return data['components']

    def get_project_metrics(self, project_key: str) -> List[Dict]:
        """Get metrics for a specific project"""
        # Ensure organization is set
        org_valid, org_msg = self._ensure_organization()
        if not org_valid:
            self.logger.error(org_msg)
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
            'sqale_rating',
            'sqale_index'
        ]
        
        url = f"{SONARCLOUD_API_URL}/measures/component"
        params = {
            'component': project_key,
            'metricKeys': ','.join(metrics),
            'organization': self.organization,
            'additionalFields': 'metrics,periods'
        }
        
        success, result = self._make_request_with_retry("GET", url, params)
        if not success:
            if "404" in str(result):
                error_msg = f"Project '{project_key}' not found or no longer exists in SonarCloud"
                self.logger.error(error_msg)
                raise requests.exceptions.HTTPError(error_msg)
            self.logger.error(f"Failed to fetch metrics: {result}")
            return []
        
        response = result
        is_valid, data = self._validate_response(response, ['component'])
        
        if not is_valid:
            self.logger.error(f"Invalid API response: {data}")
            return []
        
        component_data = data.get('component', {})
        measures = component_data.get('measures', [])
        
        if not measures:
            self.logger.warning(f"No metrics found for project {project_key}")
            return []
        
        return measures
