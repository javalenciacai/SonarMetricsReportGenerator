import requests
import streamlit as st
from config import SONARCLOUD_API_URL
import json
import logging
from functools import lru_cache
import time
from datetime import datetime, timedelta

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
        self._last_request_time = 0
        self._request_interval = 0.1  # 100ms between requests to avoid rate limiting
        self._cache_ttl = 300  # 5 minutes cache TTL

    def _rate_limit_request(self):
        """Implement rate limiting for API requests"""
        current_time = time.time()
        elapsed = current_time - self._last_request_time
        if elapsed < self._request_interval:
            time.sleep(self._request_interval - elapsed)
        self._last_request_time = time.time()

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

    @lru_cache(maxsize=128)
    def _cached_request(self, method, url, params_str):
        """Make a cached API request"""
        self._rate_limit_request()
        params = json.loads(params_str) if params_str else {}
        
        try:
            response = requests.request(method, url, headers=self.headers, params=params)
            self._log_request(method, url, params, response)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            error_msg = f"API request failed: {str(e)}"
            if hasattr(e, 'response') and hasattr(e.response, 'text'):
                self.logger.error(f"{error_msg}\nAPI Response: {e.response.text}")
            return None

    def _make_request(self, method, url, params=None, use_cache=True):
        """Make an API request with optional caching"""
        if use_cache:
            params_str = json.dumps(params, sort_keys=True) if params else ""
            cache_key = f"{method}:{url}:{params_str}"
            return self._cached_request(method, url, params_str)
        else:
            self._rate_limit_request()
            try:
                response = requests.request(method, url, headers=self.headers, params=params)
                self._log_request(method, url, params, response)
                response.raise_for_status()
                return response.json()
            except requests.exceptions.RequestException as e:
                error_msg = f"API request failed: {str(e)}"
                if hasattr(e, 'response') and hasattr(e.response, 'text'):
                    self.logger.error(f"{error_msg}\nAPI Response: {e.response.text}")
                return None

    def _check_api_version(self):
        """Check SonarCloud API version compatibility"""
        url = f"{SONARCLOUD_API_URL}/server/version"
        result = self._make_request("GET", url, use_cache=True)
        if result:
            self.api_version = result
            return True
        return False

    def validate_token(self):
        """Validate the SonarCloud token by making a test API call"""
        if not self._check_api_version():
            return False, "Could not verify API version compatibility"

        url = f"{SONARCLOUD_API_URL}/organizations/search"
        params = {'member': 'true'}
        result = self._make_request("GET", url, params=params, use_cache=False)
        
        if not result:
            return False, "Invalid token. Please check your SonarCloud token."
            
        orgs = result.get('organizations', [])
        if not orgs:
            return False, "No organizations found for this token"
        
        self.organization = orgs[0]['key']
        return True, "Token validated successfully."

    def get_projects(self, use_cache=True):
        """Get all projects for the current organization with bulk fetching"""
        if not self.organization:
            st.error("Organization not set. Please validate your token first.")
            return []
        
        projects = []
        page = 1
        page_size = 500  # Maximum page size for bulk fetching
        
        while True:
            url = f"{SONARCLOUD_API_URL}/projects/search"
            params = {
                'organization': self.organization,
                'ps': page_size,
                'p': page,
                'analyzed': 'true'
            }
            
            result = self._make_request("GET", url, params=params, use_cache=use_cache)
            if not result or 'components' not in result:
                break
                
            projects.extend(result['components'])
            
            if len(result['components']) < page_size:
                break
                
            page += 1
        
        return projects

    def get_project_metrics(self, project_key, use_cache=True):
        """Get metrics for a specific project with optimized fetching"""
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
        
        result = self._make_request("GET", url, params=params, use_cache=use_cache)
        if result and 'component' in result:
            return result['component'].get('measures', [])
        return []

    def get_project_branches(self, project_key, use_cache=True):
        """Get all branches for a specific project"""
        url = f"{SONARCLOUD_API_URL}/project_branches/list"
        params = {
            'project': project_key,
            'organization': self.organization
        }
        
        result = self._make_request("GET", url, params=params, use_cache=use_cache)
        if result:
            return result.get('branches', [])
        return []

    def clear_cache(self):
        """Clear the API request cache"""
        self._cached_request.cache_clear()
