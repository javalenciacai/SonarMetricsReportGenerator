import requests
import streamlit as st
from config import SONARCLOUD_API_URL
import json
import logging
import time
from datetime import datetime, timedelta
from functools import lru_cache
from packaging import version
import random

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
        self._max_retries = 3
        self._min_supported_version = "8.0"  # Minimum supported SonarCloud API version

    def _rate_limit_request(self):
        """Implement rate limiting for API requests"""
        current_time = time.time()
        elapsed = current_time - self._last_request_time
        if elapsed < self._request_interval:
            time.sleep(self._request_interval - elapsed)
        self._last_request_time = time.time()

    def _log_request(self, method, url, params=None, response=None, retry_count=0):
        """Log API request details for debugging"""
        if self.debug_mode:
            self.logger.debug(f"API Request: {method} {url}")
            self.logger.debug(f"Parameters: {params}")
            self.logger.debug(f"Retry Count: {retry_count}")
            if response:
                self.logger.debug(f"Status Code: {response.status_code}")
                try:
                    content = response.json() if response.text else None
                    self.logger.debug(f"Response: {content}")
                except:
                    if response.text:
                        self.logger.debug(f"Raw Response: {response.text}")
                    else:
                        self.logger.debug("No response content available")

    def _parse_version(self, version_str):
        """Parse and validate SonarCloud version string"""
        try:
            # Clean up version string and remove any quotes
            version_str = version_str.strip().strip('"')
            # Remove any non-version components (e.g., build numbers)
            cleaned_version = '.'.join(version_str.split('.')[:3])
            return version.parse(cleaned_version)
        except Exception as e:
            self.logger.error(f"Error parsing version string '{version_str}': {str(e)}")
            return None

    def _validate_version_compatibility(self, api_version):
        """Check if the API version meets minimum requirements"""
        if not api_version:
            return False, "Could not parse API version"
        
        try:
            current = self._parse_version(api_version)
            minimum = self._parse_version(self._min_supported_version)
            
            if not current or not minimum:
                return False, "Invalid version format"
            
            if current < minimum:
                return False, f"API version {api_version} is below minimum supported version {self._min_supported_version}"
            
            return True, f"API version {api_version} is compatible"
        except Exception as e:
            self.logger.error(f"Error checking version compatibility: {str(e)}")
            return False, "Version compatibility check failed"

    @lru_cache(maxsize=128)
    def _cached_request(self, method, url, params_str):
        """Make a cached API request with improved error handling"""
        self._rate_limit_request()
        params = json.loads(params_str) if params_str else {}
        
        retry_count = 0
        while retry_count < self._max_retries:
            try:
                response = requests.request(method, url, headers=self.headers, params=params)
                self._log_request(method, url, params, response, retry_count)
                
                if response.status_code == 401:
                    self.logger.error("Authentication failed. Invalid token.")
                    return None
                
                response.raise_for_status()
                
                # For version endpoint, return raw text
                if url.endswith('/server/version'):
                    return response.text.strip()
                
                return response.json()
                
            except requests.exceptions.RequestException as e:
                error_msg = f"API request failed (attempt {retry_count + 1}/{self._max_retries}): {str(e)}"
                if hasattr(e, 'response') and e.response is not None and hasattr(e.response, 'text'):
                    self.logger.error(f"{error_msg}\nAPI Response: {e.response.text}")
                else:
                    self.logger.error(error_msg)
                
                retry_count += 1
                if retry_count < self._max_retries:
                    # Exponential backoff with jitter
                    wait_time = (2 ** retry_count) + (random.random() * 0.1)
                    self.logger.info(f"Retrying in {wait_time:.2f} seconds...")
                    time.sleep(wait_time)
                else:
                    self.logger.error("Max retries exceeded")
                    return None
        return None

    def _make_request(self, method, url, params=None, use_cache=True):
        """Make an API request with optional caching"""
        if use_cache:
            params_str = json.dumps(params, sort_keys=True) if params else ""
            return self._cached_request(method, url, params_str)
        else:
            self._rate_limit_request()
            retry_count = 0
            while retry_count < self._max_retries:
                try:
                    response = requests.request(method, url, headers=self.headers, params=params)
                    self._log_request(method, url, params, response, retry_count)
                    
                    if response.status_code == 401:
                        self.logger.error("Authentication failed. Invalid token.")
                        return None
                    
                    response.raise_for_status()
                    
                    # For version endpoint, return raw text
                    if url.endswith('/server/version'):
                        return response.text.strip()
                    
                    return response.json()
                    
                except requests.exceptions.RequestException as e:
                    error_msg = f"API request failed (attempt {retry_count + 1}/{self._max_retries}): {str(e)}"
                    if hasattr(e, 'response') and e.response is not None and hasattr(e.response, 'text'):
                        self.logger.error(f"{error_msg}\nAPI Response: {e.response.text}")
                    else:
                        self.logger.error(error_msg)
                    
                    retry_count += 1
                    if retry_count < self._max_retries:
                        wait_time = (2 ** retry_count) + (random.random() * 0.1)
                        self.logger.info(f"Retrying in {wait_time:.2f} seconds...")
                        time.sleep(wait_time)
                    else:
                        self.logger.error("Max retries exceeded")
                        return None
            return None

    @lru_cache(maxsize=1)
    def _check_api_version(self):
        """Check SonarCloud API version compatibility with caching and improved error handling"""
        self.logger.info("Checking SonarCloud API version compatibility...")
        url = f"{SONARCLOUD_API_URL}/server/version"
        
        version_str = self._make_request("GET", url, use_cache=True)
        if not version_str:
            self.logger.error("Failed to retrieve API version")
            return False, "Could not connect to SonarCloud API"
        
        try:
            self.logger.info(f"Retrieved API version string: {version_str}")
            is_compatible, message = self._validate_version_compatibility(version_str)
            
            if is_compatible:
                self.api_version = version_str
                self.logger.info(f"API version check successful: {message}")
                return True, message
            else:
                self.logger.error(f"API version compatibility check failed: {message}")
                return False, message
                
        except Exception as e:
            error_msg = f"Error processing API version: {str(e)}"
            self.logger.error(error_msg)
            return False, error_msg

    def validate_token(self):
        """Validate the SonarCloud token by making a test API call"""
        # Check API version compatibility first
        version_ok, version_message = self._check_api_version()
        if not version_ok:
            self.logger.error(f"API version check failed: {version_message}")
            return False, f"API compatibility check failed: {version_message}"

        url = f"{SONARCLOUD_API_URL}/organizations/search"
        params = {'member': 'true'}
        result = self._make_request("GET", url, params=params, use_cache=False)
        
        if not result:
            self.logger.error("Token validation failed: Could not connect to SonarCloud")
            return False, "Invalid token or connection failed. Please check your SonarCloud token and internet connection."
            
        orgs = result.get('organizations', [])
        if not orgs:
            self.logger.warning("No organizations found for token")
            return False, "No organizations found for this token. Please ensure you have access to at least one organization."
        
        self.organization = orgs[0]['key']
        self.logger.info(f"Token validated successfully for organization: {self.organization}")
        return True, f"Token validated successfully for organization: {self.organization}"

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
        """Clear all API request caches"""
        self._cached_request.cache_clear()
        self._check_api_version.cache_clear()
