from datetime import datetime
import logging
from services.metric_analyzer import MetricAnalyzer
from services.report_generator import ReportGenerator

class NotificationService:
    def __init__(self, report_generator):
        self.report_generator = report_generator
        self.analyzer = MetricAnalyzer()
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        
        # Define thresholds for significant changes (in percentage)
        self.thresholds = {
            'bugs': 20,  # 20% increase
            'vulnerabilities': 20,
            'code_smells': 25,
            'coverage': -10,  # 10% decrease
            'duplicated_lines_density': 30
        }

    def check_significant_changes(self, project_key, metrics_data, historical_data):
        """Check for significant changes in metrics"""
        significant_changes = []
        
        for metric, threshold in self.thresholds.items():
            comparison = self.analyzer.calculate_period_comparison(historical_data, metric, days=1)
            if not comparison:
                continue
                
            change_percentage = comparison['change_percentage']
            
            # For coverage, we care about decreases
            if metric == 'coverage':
                if change_percentage <= threshold:  # threshold is negative for coverage
                    significant_changes.append({
                        'metric': metric,
                        'change': change_percentage,
                        'current': comparison['current_period_avg'],
                        'previous': comparison['previous_period_avg']
                    })
            # For other metrics, we care about increases
            elif change_percentage >= threshold:
                significant_changes.append({
                    'metric': metric,
                    'change': change_percentage,
                    'current': comparison['current_period_avg'],
                    'previous': comparison['previous_period_avg']
                })
        
        return significant_changes

    def format_notification_email(self, project_key, changes):
        """Format the notification email for significant changes"""
        html = f"""
        <html>
            <head>
                <style>
                    .alert {{ background: #ffe0e0; padding: 15px; margin: 10px 0; border-radius: 5px; }}
                    .metric {{ font-weight: bold; }}
                    .change-value {{ color: red; }}
                </style>
            </head>
            <body>
                <h2>⚠️ Significant Metric Changes Detected</h2>
                <p>Project: <strong>{project_key}</strong></p>
                <p>The following metrics have shown significant changes in the last 24 hours:</p>
                
                <div class="alert">
        """
        
        for change in changes:
            metric_name = change['metric'].replace('_', ' ').title()
            html += f"""
                    <div class="metric">
                        {metric_name}:
                        <span class="change-value">{change['change']:+.1f}%</span>
                        <br>
                        Current Value: {change['current']:.2f}
                        <br>
                        Previous Value: {change['previous']:.2f}
                    </div>
                    <br>
            """
            
        html += """
                </div>
                <p>Please review these changes and take necessary action if required.</p>
            </body>
        </html>
        """
        return html

    def send_notification(self, project_key, metrics_data, historical_data, recipients):
        """Check for significant changes and send notifications if needed"""
        try:
            significant_changes = self.check_significant_changes(project_key, metrics_data, historical_data)
            
            if significant_changes:
                self.logger.info(f"Significant changes detected for {project_key}")
                html_content = self.format_notification_email(project_key, significant_changes)
                
                # Create email subject with count of affected metrics
                subject = f"🚨 Alert: {len(significant_changes)} Significant Metric Changes - {project_key}"
                
                # Send the notification email
                success, message = self.report_generator.send_email_notification(
                    subject=subject,
                    html_content=html_content,
                    recipients=recipients
                )
                
                if success:
                    self.logger.info(f"Notification sent successfully for {project_key}")
                else:
                    self.logger.error(f"Failed to send notification: {message}")
                
                return success, message
            
            return True, "No significant changes detected"
            
        except Exception as e:
            error_msg = f"Error processing notifications: {str(e)}"
            self.logger.error(error_msg)
            return False, error_msg
