import requests
import json
import logging
from config import SONARCLOUD_API_URL

class SonarCloudAPI:
    def __init__(self, token):
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

    def _log_request(self, method, url, params=None, response=None):
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

    def _validate_response(self, response, expected_keys=None):
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

    def _initialize_organization(self):
        """Initialize organization from user's organizations"""
        url = f"{SONARCLOUD_API_URL}/organizations/search"
        params = {'member': 'true'}
        
        try:
            response = requests.get(url, headers=self.headers, params=params)
            self._log_request("GET", url, params, response)
            
            if response.status_code == 401:
                return False, "Invalid token. Please check your SonarCloud token."
            
            response.raise_for_status()
            is_valid, data = self._validate_response(response, ['organizations'])
            
            if not is_valid:
                return False, data
            
            orgs = data.get('organizations', [])
            if not orgs:
                return False, "No organizations found for this token"
            
            # Set the first organization as default
            self.organization = orgs[0]['key']
            return True, f"Organization initialized: {self.organization}"
            
        except requests.exceptions.RequestException as e:
            error_message = "Failed to initialize organization. Please check your connection and try again."
            self.logger.error(f"Organization initialization error: {str(e)}")
            if hasattr(e, 'response'):
                self.logger.error(f"API Response: {e.response.text}")
            return False, error_message

    def _check_api_version(self):
        """Check SonarCloud API version compatibility"""
        url = f"{SONARCLOUD_API_URL}/server/version"
        try:
            response = requests.get(url, headers=self.headers)
            self._log_request("GET", url, response=response)
            
            if response.status_code == 401:
                return False, "Invalid token. Please check your SonarCloud token."
                
            response.raise_for_status()
            self.api_version = response.text.strip()
            return True, f"API version: {self.api_version}"
        except requests.exceptions.RequestException as e:
            error_msg = f"Error checking API version: {str(e)}"
            if hasattr(e, 'response'):
                self.logger.error(f"{error_msg}\nAPI Response: {e.response.text}")
            return False, error_msg

    def validate_token(self):
        """Validate the SonarCloud token and initialize organization"""
        # First check API version
        version_valid, version_msg = self._check_api_version()
        if not version_valid:
            return False, version_msg

        # Then initialize organization
        org_valid, org_msg = self._initialize_organization()
        if not org_valid:
            return False, org_msg

        self.logger.info(f"Token validated successfully. Organization: {self.organization}")
        return True, f"Token validated successfully. Using organization: {self.organization}"

    def get_projects(self):
        """Get all projects for the current organization"""
        if not self.organization:
            success, message = self._initialize_organization()
            if not success:
                self.logger.error(message)
                return []
        
        url = f"{SONARCLOUD_API_URL}/projects/search"
        params = {
            'organization': self.organization,
            'ps': 100,
            'analyzed': 'true'
        }
        
        try:
            response = requests.get(url, headers=self.headers, params=params)
            self._log_request("GET", url, params, response)
            
            response.raise_for_status()
            is_valid, data = self._validate_response(response, ['components'])
            
            if not is_valid:
                self.logger.error(f"Invalid API response: {data}")
                return []
            
            return data['components']
            
        except requests.exceptions.RequestException as e:
            error_message = f"Failed to fetch projects: {str(e)}"
            self.logger.error(error_message)
            if hasattr(e, 'response'):
                self.logger.error(f"API Response: {e.response.text}")
            return []

    def get_project_metrics(self, project_key):
        """Get metrics for a specific project"""
        if not self.organization:
            success, message = self._initialize_organization()
            if not success:
                self.logger.error(message)
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
        
        try:
            response = requests.get(url, headers=self.headers, params=params)
            self._log_request("GET", url, params, response)
            
            if response.status_code == 404:
                error_msg = f"Project '{project_key}' not found or no longer exists in SonarCloud"
                self.logger.error(error_msg)
                raise requests.exceptions.HTTPError(error_msg, response=response)
            
            response.raise_for_status()
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
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                raise
            error_message = f"Failed to fetch metrics: {str(e)}"
            self.logger.error(error_message)
            if hasattr(e, 'response'):
                self.logger.error(f"API Response: {e.response.text}")
            return []
        except Exception as e:
            error_message = f"Error fetching metrics: {str(e)}"
            self.logger.error(error_message)
            return []
