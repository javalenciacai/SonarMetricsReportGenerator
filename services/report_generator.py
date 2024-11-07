import os
import pandas as pd
from datetime import datetime, timezone, timedelta
from database.schema import execute_query
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import json
import logging
import html

logger = logging.getLogger(__name__)

def format_project_name(name, is_active=True, is_marked_for_deletion=False):
    """Format project name with consistent status indicators"""
    name = html.escape(name)
    if not is_active:
        status_prefix = "🗑️" if is_marked_for_deletion else "⚠️"
    else:
        status_prefix = "✅"
    return f"{status_prefix} {name}"

class ReportGenerator:
    def __init__(self):
        self.smtp_server = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
        self.smtp_port = int(os.getenv('SMTP_PORT', '587'))
        self.smtp_username = os.getenv('SMTP_USERNAME')
        self.smtp_password = os.getenv('SMTP_PASSWORD')

    def _format_project_header(self, project_data):
        """Format project header with status indicators"""
        if not project_data:
            return "Unknown Project"
        
        return format_project_name(
            project_data.get('name', 'Unknown Project'),
            project_data.get('is_active', True),
            project_data.get('is_marked_for_deletion', False)
        )

    def _get_current_metrics(self, project_key=None):
        """Get current metrics with proper project name formatting"""
        query = """
        WITH RankedMetrics AS (
            SELECT 
                r.repo_key,
                r.name as project_name,
                r.is_active,
                r.is_marked_for_deletion,
                m.bugs,
                m.vulnerabilities,
                m.code_smells,
                m.coverage,
                m.duplicated_lines_density,
                m.ncloc,
                m.sqale_index,
                m.timestamp AT TIME ZONE 'UTC' as timestamp,
                ROW_NUMBER() OVER (
                    PARTITION BY r.repo_key 
                    ORDER BY m.timestamp DESC
                ) as rn
            FROM metrics m
            JOIN repositories r ON r.id = m.repository_id
            WHERE r.is_active = true
            {}
        )
        SELECT 
            repo_key,
            project_name,
            is_active,
            is_marked_for_deletion,
            bugs,
            vulnerabilities,
            code_smells,
            coverage,
            duplicated_lines_density,
            ncloc,
            sqale_index,
            timestamp
        FROM RankedMetrics
        WHERE rn = 1;
        """
        
        try:
            if project_key:
                result = execute_query(
                    query.format('AND r.repo_key = %s'),
                    (project_key,)
                )
            else:
                result = execute_query(query.format(''))
            
            metrics_data = []
            for row in result:
                data = dict(row)
                data['formatted_name'] = format_project_name(
                    data['project_name'],
                    data['is_active'],
                    data['is_marked_for_deletion']
                )
                metrics_data.append(data)
            
            return metrics_data
        except Exception as e:
            logger.error(f"Error getting current metrics: {str(e)}")
            return []

    # ... [rest of the file remains unchanged]
