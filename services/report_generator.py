import os
import pandas as pd
from datetime import datetime, timezone, timedelta
from database.schema import execute_query
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
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
        
        if not current_metrics:
            logger.warning("No current metrics available for daily report")
            return None

        report = {
            'timestamp': datetime.now(timezone.utc),
            'type': 'daily',
            'current_metrics': current_metrics,
            'changes': self._calculate_changes(current_metrics, previous_day),
            'critical_issues': self._get_critical_issues(current_metrics)
        }
        
        return self._format_daily_report(report)

    def generate_weekly_report(self, project_key=None):
        """Generate weekly report with week-over-week comparison"""
        current_metrics = self._get_current_metrics(project_key)
        previous_week = self._get_historical_metrics(project_key, days=7)
        
        if not current_metrics:
            logger.warning("No current metrics available for weekly report")
            return None

        report = {
            'timestamp': datetime.now(timezone.utc),
            'type': 'weekly',
            'current_metrics': current_metrics,
            'changes': self._calculate_changes(current_metrics, previous_week),
            'trend_analysis': self._analyze_trends(project_key),
            'executive_summary': self._generate_executive_summary(current_metrics, previous_week)
        }
        
        return self._format_weekly_report(report)

    def check_metric_changes(self, project_key=None, thresholds=None):
        """Check for significant metric changes"""
        if thresholds is None:
            thresholds = self._get_default_thresholds()

        current = self._get_current_metrics(project_key)
        if not current:
            logger.warning("No current metrics available for change detection")
            return None

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
            
            content_type = 'html' if report_format.lower() == 'HTML' else 'plain'
            msg.attach(MIMEText(content, content_type))
            
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
        """Get current metrics from database for a project or all projects"""
        query = """
        WITH RankedMetrics AS (
            SELECT 
                r.repo_key,
                r.name as project_name,
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
            
            return [dict(row) for row in result] if result else []
        except Exception as e:
            logger.error(f"Error getting current metrics: {str(e)}")
            return []

    def _get_historical_metrics(self, project_key=None, hours=None, days=None):
        """Get historical metrics from database with proper UTC handling"""
        if hours:
            interval = f"{hours} hours"
        elif days:
            interval = f"{days} days"
        else:
            return []

        query = """
        WITH HistoricalMetrics AS (
            SELECT 
                r.repo_key,
                r.name as project_name,
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
                    ORDER BY ABS(
                        EXTRACT(EPOCH FROM (
                            m.timestamp - (CURRENT_TIMESTAMP - INTERVAL '{}')
                        ))
                    )
                ) as rn
            FROM metrics m
            JOIN repositories r ON r.id = m.repository_id
            WHERE r.is_active = true
            {}
            AND m.timestamp <= CURRENT_TIMESTAMP - INTERVAL '{}'
        )
        SELECT 
            repo_key,
            project_name,
            bugs,
            vulnerabilities,
            code_smells,
            coverage,
            duplicated_lines_density,
            ncloc,
            sqale_index,
            timestamp
        FROM HistoricalMetrics
        WHERE rn = 1;
        """
        
        try:
            if project_key:
                result = execute_query(
                    query.format(interval, 'AND r.repo_key = %s', interval),
                    (project_key,)
                )
            else:
                result = execute_query(query.format(interval, '', interval))
            
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
        """Analyze metric trends from database"""
        query = """
        WITH DailyMetrics AS (
            SELECT 
                r.repo_key,
                r.name as project_name,
                DATE_TRUNC('day', m.timestamp AT TIME ZONE 'UTC') as metric_date,
                AVG(m.bugs) as bugs,
                AVG(m.vulnerabilities) as vulnerabilities,
                AVG(m.code_smells) as code_smells,
                AVG(m.coverage) as coverage,
                AVG(m.duplicated_lines_density) as duplicated_lines_density,
                AVG(m.ncloc) as ncloc
            FROM metrics m
            JOIN repositories r ON r.id = m.repository_id
            WHERE r.is_active = true
            {}
            AND m.timestamp >= CURRENT_DATE - INTERVAL '30 days'
            GROUP BY r.repo_key, r.name, DATE_TRUNC('day', m.timestamp AT TIME ZONE 'UTC')
            ORDER BY metric_date
        )
        SELECT * FROM DailyMetrics;
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
                        'direction': 'improving' if (trend < 0 if metric != 'coverage' else trend > 0) else 'worsening' if (trend > 0 if metric != 'coverage' else trend < 0) else 'stable',
                        'change_rate': abs(trend)
                    }
            
            return trends
        except Exception as e:
            logger.error(f"Error analyzing trends: {str(e)}")
            return {}

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

    def _format_daily_report(self, report_data):
        """Format daily report in HTML"""
        html_template = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Daily SonarCloud Metrics Report</title>
            {self._get_report_css()}
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>📊 Daily SonarCloud Metrics Report</h1>
                    <div class="timestamp">Generated on: {report_data['timestamp'].strftime('%Y-%m-%d %H:%M:%S UTC')}</div>
                </div>

                <div class="section-title">🎯 Current Metrics</div>
                <div class="metrics-grid">
                    {self._format_metrics_section(report_data['current_metrics'], report_data['changes'])}
                </div>

                <div class="section-title">⚠️ Critical Issues</div>
                <div class="metrics-grid">
                    {self._format_critical_section(report_data['critical_issues'])}
                </div>
            </div>
        </body>
        </html>
        """
        return html_template

    def _format_weekly_report(self, report_data):
        """Format weekly report in HTML"""
        html_template = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Weekly SonarCloud Metrics Report</title>
            {self._get_report_css()}
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>📊 Weekly SonarCloud Metrics Report</h1>
                    <div class="timestamp">Generated on: {report_data['timestamp'].strftime('%Y-%m-%d %H:%M:%S UTC')}</div>
                </div>

                <div class="executive-summary">
                    <h2>📋 Executive Summary</h2>
                    <p>{report_data['executive_summary']}</p>
                </div>

                <div class="section-title">📈 Week-over-Week Changes</div>
                <div class="metrics-grid">
                    {self._format_metrics_section(report_data['current_metrics'], report_data['changes'])}
                </div>

                <div class="section-title">📊 Trend Analysis</div>
                <div class="metrics-grid">
                    {self._format_trends_grid(report_data['trend_analysis'])}
                </div>
            </div>
        </body>
        </html>
        """
        return html_template

    def _format_metric_alerts(self, alerts):
        """Format metric alerts in HTML"""
        html_template = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Metric Change Alert</title>
            {self._get_report_css()}
        </head>
        <body>
            <div class="container">
                <div class="header alert-header">
                    <h1>⚠️ Metric Change Alert</h1>
                    <div class="timestamp">Generated on: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}</div>
                </div>

                <div class="alert-grid">
                    {self._format_alerts_grid(alerts)}
                </div>
            </div>
        </body>
        </html>
        """
        return html_template

    def _format_metrics_section(self, metrics, changes=None):
        """Format metrics section with styling"""
        if not metrics:
            return "<div class='metric-card'>No metrics data available</div>"

        metrics_html = []
        metrics_icons = {
            'bugs': '🐛',
            'vulnerabilities': '⚠️',
            'code_smells': '🔍',
            'coverage': '📊',
            'duplicated_lines_density': '📝',
            'ncloc': '📏'
        }

        for metric, icon in metrics_icons.items():
            if metric in metrics[0]:
                value = metrics[0][metric]
                formatted_value = f"{value:.1f}%" if metric in ['coverage', 'duplicated_lines_density'] else value
                
                change_info = ""
                if changes and metric in changes:
                    change = changes[metric]
                    change_class = 'trend-positive' if change['change'] < 0 else 'trend-negative' if change['change'] > 0 else 'trend-neutral'
                    change_info = f"""
                        <div class="metric-change {change_class}">
                            {change['change_percent']:+.1f}%
                        </div>
                    """
                
                metrics_html.append(f"""
                    <div class="metric-card">
                        <div class="metric-header">
                            <div class="metric-title">{icon} {metric.replace('_', ' ').title()}</div>
                            {change_info}
                        </div>
                        <div class="metric-value">{formatted_value}</div>
                    </div>
                """)

        return "\n".join(metrics_html)

    def _format_critical_section(self, issues):
        """Format critical issues section"""
        if not issues:
            return "<div class='metric-card'>No critical issues data available</div>"

        issues_html = []
        severity_icons = {
            'high_severity_bugs': '🐛',
            'critical_vulnerabilities': '⚠️',
            'major_code_smells': '🔍'
        }
        
        for issue_type, icon in severity_icons.items():
            count = issues[issue_type]
            severity_class = 'trend-negative' if count > 0 else 'trend-positive'
            
            issues_html.append(f"""
                <div class="metric-card">
                    <div class="metric-header">
                        <div class="metric-title">{icon} {issue_type.replace('_', ' ').title()}</div>
                        <div class="metric-change {severity_class}">
                            {count}
                        </div>
                    </div>
                    <div class="metric-value">{count}</div>
                </div>
            """)

        return "\n".join(issues_html)

    def _format_trends_grid(self, trends):
        """Format trends section"""
        if not trends:
            return "<div class='metric-card'>No trend data available</div>"

        trend_html = []
        for metric, data in trends.items():
            trend_class = {
                'improving': 'trend-positive',
                'worsening': 'trend-negative',
                'stable': 'trend-neutral'
            }.get(data['direction'], 'trend-neutral')

            trend_icon = {
                'improving': '📉',
                'worsening': '📈',
                'stable': '📊'
            }.get(data['direction'], '📊')

            trend_html.append(f"""
                <div class="metric-card">
                    <div class="metric-header">
                        <div class="metric-title">{trend_icon} {metric.replace('_', ' ').title()}</div>
                        <div class="metric-change {trend_class}">
                            {data['direction'].title()}
                        </div>
                    </div>
                    <div class="metric-value">
                        Change Rate: {data['change_rate']:.2f}/day
                    </div>
                </div>
            """)

        return "\n".join(trend_html)

    def _format_alerts_grid(self, alerts):
        """Format alerts grid"""
        alerts_html = []
        for alert in alerts:
            trend_class = 'trend-negative' if alert['change'] > 0 else 'trend-positive'
            alerts_html.append(f"""
                <div class="metric-card alert-card">
                    <div class="metric-header">
                        <div class="metric-title">⚠️ {alert['metric'].replace('_', ' ').title()}</div>
                        <div class="metric-change {trend_class}">
                            {alert['change_percent']:+.1f}%
                        </div>
                    </div>
                    <div class="metric-value">{alert['current']}</div>
                    <div class="metric-detail">Previous: {alert['previous']}</div>
                    <div class="metric-detail">Threshold: {alert['threshold']}</div>
                </div>
            """)
        return "\n".join(alerts_html)

    def _generate_executive_summary(self, current, previous):
        """Generate executive summary"""
        if not current or not previous:
            return "Insufficient data for executive summary"
        
        changes = self._calculate_changes(current, previous)
        
        summary = []
        for metric, data in changes.items():
            if abs(data['change_percent']) >= 5:
                direction = "improved" if data['change'] < 0 else "increased"
                summary.append(f"{metric.replace('_', ' ').title()} has {direction} by {abs(data['change_percent']):.1f}%")
        
        return " | ".join(summary) if summary else "No significant changes detected"

    def _get_default_thresholds(self):
        """Get default thresholds"""
        return {
            'bugs': 5,
            'vulnerabilities': 3,
            'code_smells': 10,
            'coverage': -5,
            'duplicated_lines_density': 5
        }

    def _get_report_css(self):
        """Get report CSS styling"""
        return """
            <style>
                :root {
                    --bg-primary: #1A1F25;
                    --bg-secondary: #2D3748;
                    --text-primary: #FAFAFA;
                    --text-secondary: #A0AEC0;
                    --accent-green: #48BB78;
                    --accent-red: #F56565;
                    --accent-yellow: #ECC94B;
                }
                
                body {
                    font-family: 'SF Pro Display', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    background-color: var(--bg-primary);
                    color: var(--text-secondary);
                    line-height: 1.6;
                    margin: 0;
                    padding: 2rem;
                }
                
                .container {
                    max-width: 1200px;
                    margin: 0 auto;
                }
                
                .header {
                    padding: 2rem;
                    background: var(--bg-secondary);
                    border-radius: 12px;
                    margin-bottom: 2rem;
                    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
                }
                
                .header h1 {
                    color: var(--text-primary);
                    margin: 0;
                    font-size: 2rem;
                    display: flex;
                    align-items: center;
                    gap: 0.5rem;
                }
                
                .timestamp {
                    color: var(--text-secondary);
                    font-size: 0.9rem;
                    margin-top: 0.5rem;
                }
                
                .metrics-grid {
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
                    gap: 1.5rem;
                    margin: 2rem 0;
                }
                
                .metric-card {
                    background: var(--bg-secondary);
                    border-radius: 10px;
                    padding: 1.5rem;
                    transition: transform 0.2s ease;
                    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
                }
                
                .metric-card:hover {
                    transform: translateY(-2px);
                    box-shadow: 0 4px 8px rgba(0, 0, 0, 0.15);
                }
                
                .metric-header {
                    display: flex;
                    align-items: center;
                    justify-content: space-between;
                    margin-bottom: 1rem;
                }
                
                .metric-title {
                    color: var(--text-secondary);
                    font-size: 0.9rem;
                    display: flex;
                    align-items: center;
                    gap: 0.5rem;
                }
                
                .metric-value {
                    color: var(--text-primary);
                    font-size: 1.8rem;
                    font-family: 'SF Mono', 'Consolas', monospace;
                    font-weight: 600;
                }
                
                .metric-change {
                    font-size: 0.9rem;
                    padding: 0.25rem 0.75rem;
                    border-radius: 12px;
                    display: inline-flex;
                    align-items: center;
                    gap: 0.25rem;
                }
                
                .trend-positive {
                    color: var(--accent-green);
                    background: rgba(72, 187, 120, 0.1);
                }
                
                .trend-negative {
                    color: var(--accent-red);
                    background: rgba(245, 101, 101, 0.1);
                }
                
                .trend-neutral {
                    color: var(--text-secondary);
                    background: rgba(160, 174, 192, 0.1);
                }
                
                .section-title {
                    color: var(--text-primary);
                    font-size: 1.5rem;
                    margin: 2rem 0 1rem;
                    padding-bottom: 0.5rem;
                    border-bottom: 2px solid var(--bg-secondary);
                }
                
                .executive-summary {
                    background: var(--bg-secondary);
                    border-radius: 10px;
                    padding: 1.5rem;
                    margin: 2rem 0;
                    border-left: 4px solid var(--accent-green);
                }
                
                .executive-summary h2 {
                    color: var(--text-primary);
                    margin: 0 0 1rem 0;
                }
                
                .metric-detail {
                    color: var(--text-secondary);
                    font-size: 0.9rem;
                    margin-top: 0.5rem;
                }
                
                .alert-header {
                    border-left: 4px solid var(--accent-yellow);
                }
                
                .alert-card {
                    border-left: 4px solid var(--accent-red);
                }
                
                .alert-grid {
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
                    gap: 1.5rem;
                    margin: 2rem 0;
                }
            </style>
        """

    def get_report_recipients(self, report_type):
        """Get recipients for a specific report type"""
        query = """
        SELECT recipients
        FROM report_schedules
        WHERE report_type = %s AND is_active = true;
        """
        try:
            result = execute_query(query, (report_type,))
            if result:
                recipients = set()
                for row in result:
                    if isinstance(row[0], str):
                        recipients.update(json.loads(row[0]))
                    else:
                        recipients.update(row[0])
                return list(recipients)
            return []
        except Exception as e:
            logger.error(f"Error getting report recipients: {str(e)}")
            return []