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

    def _format_daily_report(self, report_data):
        """Format daily report in HTML with modern tech styling"""
        css = """
        <style>
            body {
                font-family: 'SF Pro Display', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
                background: #1A1F25;
                color: #A0AEC0;
                line-height: 1.6;
                margin: 0;
                padding: 20px;
            }
            .report-container {
                max-width: 1200px;
                margin: 0 auto;
                padding: 30px;
                background: #1A1F25;
                border-radius: 12px;
                box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            }
            .header {
                border-bottom: 2px solid #2D3748;
                padding-bottom: 20px;
                margin-bottom: 30px;
            }
            h1, h2, h3 {
                color: #FAFAFA;
                font-weight: 600;
                margin: 0 0 20px 0;
            }
            h1 { font-size: 28px; }
            h2 { font-size: 24px; }
            h3 { 
                font-size: 20px;
                display: flex;
                align-items: center;
                gap: 10px;
            }
            .timestamp {
                color: #718096;
                font-size: 14px;
                margin-bottom: 20px;
            }
            .metrics-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
                gap: 20px;
                margin: 20px 0;
            }
            .metric-card {
                background: #2D3748;
                border-radius: 8px;
                padding: 20px;
                transition: transform 0.2s;
            }
            .metric-card:hover {
                transform: translateY(-2px);
            }
            .metric-title {
                color: #A0AEC0;
                font-size: 14px;
                margin-bottom: 10px;
                display: flex;
                align-items: center;
                gap: 8px;
            }
            .metric-value {
                color: #FAFAFA;
                font-size: 24px;
                font-family: 'SF Mono', 'Consolas', monospace;
                font-weight: 600;
            }
            .metric-change {
                font-size: 14px;
                margin-top: 8px;
                padding: 4px 8px;
                border-radius: 4px;
                display: inline-block;
            }
            .positive { color: #48BB78; }
            .negative { color: #F56565; }
            .neutral { color: #A0AEC0; }
            .trend-indicator {
                font-size: 16px;
                margin-left: 8px;
            }
            .critical-section {
                background: #2D3748;
                border-radius: 8px;
                padding: 20px;
                margin-top: 30px;
            }
            .status-badge {
                display: inline-block;
                padding: 4px 12px;
                border-radius: 12px;
                font-size: 12px;
                font-weight: 500;
                margin-left: 10px;
            }
            .status-critical {
                background: #F56565;
                color: #FAFAFA;
            }
            .status-warning {
                background: #ECC94B;
                color: #1A1F25;
            }
            .status-good {
                background: #48BB78;
                color: #FAFAFA;
            }
            .sparkline {
                display: inline-block;
                margin-left: 10px;
                vertical-align: middle;
            }
            .metric-header {
                display: flex;
                align-items: center;
                justify-content: space-between;
                margin-bottom: 15px;
            }
            .period-comparison {
                font-size: 12px;
                padding: 4px 8px;
                border-radius: 4px;
                background: rgba(0, 0, 0, 0.2);
            }
            .interactive-chart {
                margin-top: 20px;
                background: rgba(45, 55, 72, 0.5);
                border-radius: 8px;
                padding: 15px;
            }
        </style>
        """

        return f"""
        {css}
        <div class="report-container">
            <div class="header">
                <h1>📊 Daily SonarCloud Metrics Report</h1>
                <div class="timestamp">Generated on: {report_data['timestamp'].strftime('%Y-%m-%d %H:%M:%S UTC')}</div>
            </div>

            <div class="metrics-grid">
                <div class="metric-card">
                    <h3>🎯 Current Metrics</h3>
                    {self._format_metrics_grid(report_data['current_metrics'])}
                </div>

                <div class="metric-card">
                    <h3>📈 24-Hour Changes</h3>
                    {self._format_changes_grid(report_data['changes'])}
                </div>
            </div>

            <div class="critical-section">
                <h3>⚠️ Critical Issues</h3>
                {self._format_critical_issues_grid(report_data['critical_issues'])}
            </div>
        </div>
        """

    def _format_weekly_report(self, report_data):
        """Format weekly report in HTML with modern tech styling"""
        css = """
        <style>
            body {
                font-family: 'SF Pro Display', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
                background: #1A1F25;
                color: #A0AEC0;
                line-height: 1.6;
                margin: 0;
                padding: 20px;
            }
            .report-container {
                max-width: 1200px;
                margin: 0 auto;
                padding: 30px;
                background: #1A1F25;
                border-radius: 12px;
                box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            }
            .header {
                border-bottom: 2px solid #2D3748;
                padding-bottom: 20px;
                margin-bottom: 30px;
            }
            .executive-summary {
                background: #2D3748;
                border-radius: 8px;
                padding: 25px;
                margin: 20px 0;
                border-left: 4px solid #48BB78;
            }
            h1, h2, h3 {
                color: #FAFAFA;
                font-weight: 600;
                margin: 0 0 20px 0;
            }
            h1 { font-size: 28px; }
            h2 { font-size: 24px; }
            h3 { 
                font-size: 20px;
                display: flex;
                align-items: center;
                gap: 10px;
            }
            .timestamp {
                color: #718096;
                font-size: 14px;
                margin-bottom: 20px;
            }
            .metrics-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
                gap: 25px;
                margin: 25px 0;
            }
            .metric-card {
                background: #2D3748;
                border-radius: 8px;
                padding: 25px;
                transition: transform 0.2s;
            }
            .metric-card:hover {
                transform: translateY(-2px);
            }
            .trend-card {
                background: linear-gradient(45deg, #2D3748, #1A1F25);
                border-radius: 8px;
                padding: 25px;
                margin-top: 30px;
            }
            .trend-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 20px;
            }
            .trend-item {
                padding: 15px;
                background: rgba(45, 55, 72, 0.5);
                border-radius: 6px;
            }
            .trend-icon {
                font-size: 24px;
                margin-right: 10px;
            }
            .trend-improving { color: #48BB78; }
            .trend-worsening { color: #F56565; }
            .trend-stable { color: #ECC94B; }
            .sparkline {
                display: inline-block;
                margin-left: 10px;
                vertical-align: middle;
            }
            .metric-header {
                display: flex;
                align-items: center;
                justify-content: space-between;
                margin-bottom: 15px;
            }
            .period-comparison {
                font-size: 12px;
                padding: 4px 8px;
                border-radius: 4px;
                background: rgba(0, 0, 0, 0.2);
            }
            .interactive-chart {
                margin-top: 20px;
                background: rgba(45, 55, 72, 0.5);
                border-radius: 8px;
                padding: 15px;
            }
        </style>
        """

        return f"""
        {css}
        <div class="report-container">
            <div class="header">
                <h1>📊 Weekly SonarCloud Metrics Report</h1>
                <div class="timestamp">Generated on: {report_data['timestamp'].strftime('%Y-%m-%d %H:%M:%S UTC')}</div>
            </div>

            <div class="executive-summary">
                <h2>📋 Executive Summary</h2>
                <p>{report_data['executive_summary']}</p>
            </div>

            <div class="metrics-grid">
                <div class="metric-card">
                    <h3>🎯 Current Metrics</h3>
                    {self._format_metrics_grid(report_data['current_metrics'])}
                </div>

                <div class="metric-card">
                    <h3>📈 Week-over-Week Changes</h3>
                    {self._format_changes_grid(report_data['changes'])}
                </div>
            </div>

            <div class="trend-card">
                <h3>📊 Trend Analysis</h3>
                <div class="trend-grid">
                    {self._format_trends_grid(report_data['trend_analysis'])}
                </div>
            </div>

            <div class="interactive-chart">
                <h3>📈 Interactive Metrics History</h3>
                <!-- Placeholder for interactive chart - implemented in the UI -->
            </div>
        </div>
        """

    def _format_metrics_grid(self, metrics):
        """Format metrics with modern grid layout"""
        if not metrics:
            return "<p class='neutral'>No metrics data available</p>"

        items = []
        metrics_icons = {
            'bugs': '🐛',
            'vulnerabilities': '⚠️',
            'code_smells': '🔍',
            'coverage': '📊',
            'duplicated_lines_density': '📝',
            'ncloc': '📏'
        }

        for metric in metrics[0]:
            if metric in metrics_icons:
                value = metrics[0][metric]
                formatted_value = f"{value:.1f}%" if metric in ['coverage', 'duplicated_lines_density'] else value
                items.append(f"""
                <div class="metric-item">
                    <div class="metric-header">
                        <span class="metric-title">{metrics_icons[metric]} {metric.replace('_', ' ').title()}</span>
                    </div>
                    <div class="metric-value">{formatted_value}</div>
                </div>
                """)

        return "\n".join(items)

    def _format_changes_grid(self, changes):
        """Format changes with modern styling"""
        if not changes:
            return "<p class='neutral'>No changes data available</p>"

        items = []
        for metric, data in changes.items():
            direction = "+" if data['change'] > 0 else ""
            status_class = "negative" if data['change'] > 0 else "positive" if data['change'] < 0 else "neutral"
            trend_icon = "📈" if data['change'] > 0 else "📉" if data['change'] < 0 else "📊"

            items.append(f"""
            <div class="metric-item">
                <div class="metric-header">
                    <span class="metric-title">{metric.replace('_', ' ').title()}</span>
                    <span class="trend-indicator">{trend_icon}</span>
                </div>
                <div class="metric-value {status_class}">
                    {direction}{data['change']:.1f}
                </div>
                <div class="metric-change {status_class}">
                    {direction}{data['change_percent']:.1f}%
                </div>
                <div class="period-comparison">
                    Previous: {data['previous']:.1f} → Current: {data['current']:.1f}
                </div>
            </div>
            """)

        return "\n".join(items)

    def _format_critical_issues_grid(self, issues):
        """Format critical issues with modern styling"""
        def get_severity_badge(count):
            if count > 10:
                return 'status-critical'
            elif count > 5:
                return 'status-warning'
            return 'status-good'

        def get_severity_icon(count):
            if count > 10:
                return '🔴'
            elif count > 5:
                return '🟡'
            return '🟢'

        items = []
        for issue_type, count in issues.items():
            badge_class = get_severity_badge(count)
            status_icon = get_severity_icon(count)
            
            items.append(f"""
            <div class="metric-card">
                <div class="metric-header">
                    <span class="metric-title">{issue_type.replace('_', ' ').title()}</span>
                    <span class="status-badge {badge_class}">{status_icon} {count}</span>
                </div>
                <div class="metric-value">
                    {count}
                    <div class="period-comparison">
                        Severity: {badge_class.replace('status-', '').title()}
                    </div>
                </div>
            </div>
            """)

        return "\n".join(items)

    def _format_trends_grid(self, trends):
        """Format trends with modern styling"""
        if not trends:
            return "<p class='neutral'>No trend data available</p>"

        items = []
        for metric, data in trends.items():
            trend_class = {
                'improving': 'trend-improving',
                'worsening': 'trend-worsening',
                'stable': 'trend-stable'
            }.get(data['direction'], 'trend-stable')

            trend_icon = {
                'improving': '📉',
                'worsening': '📈',
                'stable': '📊'
            }.get(data['direction'], '📊')

            items.append(f"""
            <div class="trend-item">
                <div class="metric-header">
                    <span class="metric-title">{metric.replace('_', ' ').title()}</span>
                    <span class="trend-icon {trend_class}">{trend_icon}</span>
                </div>
                <div class="metric-value {trend_class}">
                    {data['direction'].title()}
                    <div class="metric-change">
                        Change Rate: {data['change_rate']:.2f}/day
                    </div>
                </div>
            </div>
            """)

        return "\n".join(items)
