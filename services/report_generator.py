import pandas as pd
from datetime import datetime, timezone, timedelta
from database.schema import execute_query
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import json
import logging

logger = logging.getLogger(__name__)

class ReportGenerator:
    def __init__(self):
        self.smtp_server = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
        self.smtp_port = int(os.getenv('SMTP_PORT', '587'))
        self.smtp_username = os.getenv('SMTP_USERNAME')
        self.smtp_password = os.getenv('SMTP_PASSWORD')

    def generate_daily_report(self, project_key=None):
        """Generate daily report with 24-hour comparison"""
        current_metrics = self._get_current_metrics(project_key)
        previous_day = self._get_historical_metrics(project_key, hours=24)
        
        report = {
            'timestamp': datetime.now(timezone.utc),
            'type': 'daily',
            'current_metrics': current_metrics,
            'changes': self._calculate_changes(current_metrics, previous_day),
            'critical_issues': self._get_critical_issues(current_metrics)
        }
        
        return self._format_report(report)

    def generate_weekly_report(self, project_key=None):
        """Generate weekly report with week-over-week comparison"""
        current_metrics = self._get_current_metrics(project_key)
        previous_week = self._get_historical_metrics(project_key, days=7)
        
        report = {
            'timestamp': datetime.now(timezone.utc),
            'type': 'weekly',
            'current_metrics': current_metrics,
            'changes': self._calculate_changes(current_metrics, previous_week),
            'trend_analysis': self._analyze_trends(project_key),
            'executive_summary': self._generate_executive_summary(current_metrics, previous_week)
        }
        
        return self._format_report(report)

    def check_metric_changes(self, project_key=None, thresholds=None):
        """Check for significant metric changes"""
        if thresholds is None:
            thresholds = self._get_default_thresholds()

        current = self._get_current_metrics(project_key)
        previous = self._get_historical_metrics(project_key, hours=4)
        
        changes = self._calculate_changes(current, previous)
        alerts = self._check_thresholds(changes, thresholds)
        
        if alerts:
            return self._format_metric_alerts(alerts)
        return None

    def send_email(self, recipients, subject, content, report_format='HTML'):
        """Send email using configured SMTP settings"""
        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.smtp_username
            msg['To'] = ', '.join(recipients)
            
            msg.attach(MIMEText(content, report_format.lower()))
            
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_username, self.smtp_password)
                server.send_message(msg)
            
            return True
        except Exception as e:
            logger.error(f"Error sending email: {str(e)}")
            return False

    def test_smtp_connection(self):
        """Test SMTP connection and credentials"""
        try:
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_username, self.smtp_password)
            return True, "SMTP connection successful"
        except Exception as e:
            return False, f"SMTP connection failed: {str(e)}"

    def _get_current_metrics(self, project_key=None):
        """Get current metrics for a project or all projects"""
        query = """
        SELECT 
            r.repo_key,
            r.name,
            m.*
        FROM metrics m
        JOIN repositories r ON r.id = m.repository_id
        WHERE r.is_active = true
        {}
        AND m.timestamp = (
            SELECT MAX(timestamp)
            FROM metrics m2
            WHERE m2.repository_id = m.repository_id
        );
        """
        
        try:
            if project_key:
                result = execute_query(
                    query.format('AND r.repo_key = %s'),
                    (project_key,)
                )
            else:
                result = execute_query(query.format(''))
            
            return [dict(row) for row in result] if result else []
        except Exception as e:
            logger.error(f"Error getting current metrics: {str(e)}")
            return []

    def _get_historical_metrics(self, project_key=None, hours=None, days=None):
        """Get historical metrics for comparison"""
        if hours:
            interval = f"{hours} hours"
        elif days:
            interval = f"{days} days"
        else:
            return []

        query = """
        SELECT 
            r.repo_key,
            r.name,
            m.*
        FROM metrics m
        JOIN repositories r ON r.id = m.repository_id
        WHERE r.is_active = true
        {}
        AND m.timestamp <= CURRENT_TIMESTAMP - INTERVAL '{}'
        AND m.timestamp > CURRENT_TIMESTAMP - INTERVAL '{}' - INTERVAL '1 hour'
        ORDER BY m.timestamp DESC;
        """
        
        try:
            if project_key:
                result = execute_query(
                    query.format('AND r.repo_key = %s', interval, interval),
                    (project_key,)
                )
            else:
                result = execute_query(query.format('', interval, interval))
            
            return [dict(row) for row in result] if result else []
        except Exception as e:
            logger.error(f"Error getting historical metrics: {str(e)}")
            return []

    def _calculate_changes(self, current, previous):
        """Calculate changes between current and previous metrics"""
        changes = {}
        metrics_to_compare = [
            'bugs', 'vulnerabilities', 'code_smells', 
            'coverage', 'duplicated_lines_density', 'ncloc'
        ]
        
        for metric in metrics_to_compare:
            try:
                current_value = float(current[0][metric]) if current else 0
                previous_value = float(previous[0][metric]) if previous else 0
                
                if previous_value != 0:
                    change_percent = ((current_value - previous_value) / previous_value) * 100
                else:
                    change_percent = 100 if current_value > 0 else 0
                
                changes[metric] = {
                    'previous': previous_value,
                    'current': current_value,
                    'change': current_value - previous_value,
                    'change_percent': change_percent
                }
            except (KeyError, IndexError, TypeError):
                continue
        
        return changes

    def _get_critical_issues(self, metrics):
        """Extract critical issues from metrics"""
        critical = {
            'high_severity_bugs': 0,
            'critical_vulnerabilities': 0,
            'major_code_smells': 0
        }
        
        if metrics:
            critical['high_severity_bugs'] = int(metrics[0].get('bugs', 0))
            critical['critical_vulnerabilities'] = int(metrics[0].get('vulnerabilities', 0))
            critical['major_code_smells'] = int(metrics[0].get('code_smells', 0))
        
        return critical

    def _analyze_trends(self, project_key=None):
        """Analyze metric trends over time"""
        query = """
        SELECT 
            r.repo_key,
            r.name,
            m.*,
            m.timestamp::date as date
        FROM metrics m
        JOIN repositories r ON r.id = m.repository_id
        WHERE r.is_active = true
        {}
        AND m.timestamp >= CURRENT_DATE - INTERVAL '30 days'
        ORDER BY m.timestamp;
        """
        
        try:
            if project_key:
                result = execute_query(
                    query.format('AND r.repo_key = %s'),
                    (project_key,)
                )
            else:
                result = execute_query(query.format(''))
            
            if not result:
                return {}
            
            df = pd.DataFrame([dict(row) for row in result])
            trends = {}
            
            for metric in ['bugs', 'vulnerabilities', 'code_smells', 'coverage']:
                if metric in df.columns:
                    trend = df[metric].diff().mean()
                    trends[metric] = {
                        'direction': 'improving' if trend < 0 else 'worsening' if trend > 0 else 'stable',
                        'change_rate': abs(trend)
                    }
            
            return trends
        except Exception as e:
            logger.error(f"Error analyzing trends: {str(e)}")
            return {}

    def _generate_executive_summary(self, current, previous):
        """Generate executive summary comparing current state with previous period"""
        if not current or not previous:
            return "Insufficient data for executive summary"
        
        changes = self._calculate_changes(current, previous)
        
        summary = []
        for metric, data in changes.items():
            if abs(data['change_percent']) >= 5:  # Only report significant changes
                direction = "improved" if data['change'] < 0 else "increased"
                summary.append(f"{metric.replace('_', ' ').title()} has {direction} by {abs(data['change_percent']):.1f}%")
        
        return " | ".join(summary) if summary else "No significant changes detected"

    def _get_default_thresholds(self):
        """Get default thresholds for metric changes"""
        return {
            'bugs': 5,
            'vulnerabilities': 3,
            'code_smells': 10,
            'coverage': -5,
            'duplicated_lines_density': 5
        }

    def _check_thresholds(self, changes, thresholds):
        """Check if changes exceed thresholds"""
        alerts = []
        
        for metric, data in changes.items():
            if metric in thresholds:
                threshold = thresholds[metric]
                if abs(data['change']) >= threshold:
                    alerts.append({
                        'metric': metric,
                        'change': data['change'],
                        'threshold': threshold,
                        'previous': data['previous'],
                        'current': data['current'],
                        'change_percent': data['change_percent']
                    })
        
        return alerts

    def _format_report(self, report_data):
        """Format report data based on type"""
        if report_data['type'] == 'daily':
            return self._format_daily_report(report_data)
        elif report_data['type'] == 'weekly':
            return self._format_weekly_report(report_data)
        return json.dumps(report_data, indent=2)

    def _format_daily_report(self, report_data):
        """Format daily report in HTML"""
        template = """
        <h2>Daily SonarCloud Metrics Report</h2>
        <p>Generated on: {timestamp}</p>
        
        <h3>Current Metrics</h3>
        <ul>
        {current_metrics}
        </ul>
        
        <h3>24-Hour Changes</h3>
        <ul>
        {changes}
        </ul>
        
        <h3>Critical Issues</h3>
        <ul>
        {critical_issues}
        </ul>
        """
        
        return template.format(
            timestamp=report_data['timestamp'].strftime('%Y-%m-%d %H:%M:%S UTC'),
            current_metrics=self._format_metrics_list(report_data['current_metrics']),
            changes=self._format_changes_list(report_data['changes']),
            critical_issues=self._format_issues_list(report_data['critical_issues'])
        )

    def _format_weekly_report(self, report_data):
        """Format weekly report in HTML"""
        template = """
        <h2>Weekly SonarCloud Metrics Report</h2>
        <p>Generated on: {timestamp}</p>
        
        <h3>Executive Summary</h3>
        <p>{executive_summary}</p>
        
        <h3>Current Metrics</h3>
        <ul>
        {current_metrics}
        </ul>
        
        <h3>Week-over-Week Changes</h3>
        <ul>
        {changes}
        </ul>
        
        <h3>Trend Analysis</h3>
        <ul>
        {trends}
        </ul>
        """
        
        return template.format(
            timestamp=report_data['timestamp'].strftime('%Y-%m-%d %H:%M:%S UTC'),
            executive_summary=report_data['executive_summary'],
            current_metrics=self._format_metrics_list(report_data['current_metrics']),
            changes=self._format_changes_list(report_data['changes']),
            trends=self._format_trends_list(report_data['trend_analysis'])
        )

    def _format_metrics_list(self, metrics):
        """Format metrics as HTML list items"""
        if not metrics:
            return "<li>No metrics data available</li>"
        
        items = []
        for metric in metrics:
            items.extend([
                f"<li>Bugs: {metric.get('bugs', 0)}</li>",
                f"<li>Vulnerabilities: {metric.get('vulnerabilities', 0)}</li>",
                f"<li>Code Smells: {metric.get('code_smells', 0)}</li>",
                f"<li>Coverage: {metric.get('coverage', 0):.1f}%</li>",
                f"<li>Duplication: {metric.get('duplicated_lines_density', 0):.1f}%</li>"
            ])
        return "\n".join(items)

    def _format_changes_list(self, changes):
        """Format changes as HTML list items"""
        if not changes:
            return "<li>No changes data available</li>"
        
        items = []
        for metric, data in changes.items():
            direction = "+" if data['change'] > 0 else ""
            items.append(
                f"<li>{metric.replace('_', ' ').title()}: {direction}{data['change']:.1f} "
                f"({direction}{data['change_percent']:.1f}%)</li>"
            )
        return "\n".join(items)

    def _format_issues_list(self, issues):
        """Format issues as HTML list items"""
        return "\n".join([
            f"<li>High Severity Bugs: {issues['high_severity_bugs']}</li>",
            f"<li>Critical Vulnerabilities: {issues['critical_vulnerabilities']}</li>",
            f"<li>Major Code Smells: {issues['major_code_smells']}</li>"
        ])

    def _format_trends_list(self, trends):
        """Format trends as HTML list items"""
        if not trends:
            return "<li>No trend data available</li>"
        
        items = []
        for metric, data in trends.items():
            items.append(
                f"<li>{metric.replace('_', ' ').title()}: {data['direction'].title()} "
                f"(Rate: {data['change_rate']:.2f}/day)</li>"
            )
        return "\n".join(items)

    def _format_metric_alerts(self, alerts):
        """Format metric alerts into HTML with enhanced styling"""
        css_styles = """
        <style>
            .alert-container {
                background: #1A1F25;
                border: 1px solid #2D3748;
                border-radius: 8px;
                padding: 20px;
                margin: 20px 0;
                font-family: Arial, sans-serif;
            }
            .alert-header {
                color: #FAFAFA;
                font-size: 24px;
                margin-bottom: 15px;
                border-bottom: 1px solid #2D3748;
                padding-bottom: 10px;
            }
            .alert-timestamp {
                color: #A0AEC0;
                font-size: 14px;
                margin-bottom: 20px;
            }
            .alert-list {
                list-style: none;
                padding: 0;
                margin: 0;
            }
            .alert-item {
                background: #2D3748;
                border-radius: 6px;
                padding: 15px;
                margin-bottom: 10px;
                color: #FAFAFA;
            }
            .alert-title {
                font-size: 18px;
                font-weight: bold;
                margin-bottom: 10px;
            }
            .metric-change {
                display: flex;
                justify-content: space-between;
                margin-top: 10px;
            }
            .change-indicator {
                padding: 4px 8px;
                border-radius: 4px;
                font-weight: bold;
            }
            .change-negative { background: #38A169; color: #FAFAFA; }
            .change-positive { background: #E53E3E; color: #FAFAFA; }
            .metric-details {
                color: #A0AEC0;
                font-size: 14px;
                margin-top: 8px;
            }
        </style>
        """
        
        template = f"""
        {css_styles}
        <div class="alert-container">
            <h2 class="alert-header">⚠️ SonarCloud Metric Change Alert</h2>
            <div class="alert-timestamp">
                Generated on: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}
            </div>
            <p>The following significant changes have been detected:</p>
            <ul class="alert-list">
            {{alert_items}}
            </ul>
        </div>
        """
        
        alert_items = []
        for alert in alerts:
            metric_name = alert['metric'].replace('_', ' ').title()
            is_improvement = (
                (alert['change'] < 0 and alert['metric'] not in ['coverage']) or
                (alert['change'] > 0 and alert['metric'] in ['coverage'])
            )
            change_class = 'change-negative' if is_improvement else 'change-positive'
            change_symbol = '↓' if alert['change'] < 0 else '↑'
            
            alert_items.append(f"""
                <li class="alert-item">
                    <div class="alert-title">{metric_name}</div>
                    <div class="metric-change">
                        <span>Change: 
                            <span class="change-indicator {change_class}">
                                {change_symbol} {abs(alert['change']):.1f}
                            </span>
                        </span>
                        <span>
                            {abs(alert['change_percent']):.1f}%
                        </span>
                    </div>
                    <div class="metric-details">
                        Previous: {alert['previous']:.1f} → Current: {alert['current']:.1f}
                        (Threshold: {alert['threshold']})
                    </div>
                </li>
            """)
        
        return template.format(alert_items="\n".join(alert_items))
