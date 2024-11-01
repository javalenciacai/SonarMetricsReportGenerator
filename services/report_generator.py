import pandas as pd
from datetime import datetime, timedelta
from services.sonarcloud import SonarCloudAPI
from services.metrics_processor import MetricsProcessor
from services.metric_analyzer import MetricAnalyzer
import logging
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication

class ReportGenerator:
    def __init__(self, sonar_api):
        self.sonar_api = sonar_api
        self.metrics_processor = MetricsProcessor()
        self.analyzer = MetricAnalyzer()
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        self.smtp_config = {
            'server': os.getenv('SMTP_SERVER', 'smtp.gmail.com'),
            'port': int(os.getenv('SMTP_PORT', '587')),
            'username': os.getenv('SMTP_USERNAME'),
            'password': os.getenv('SMTP_PASSWORD')
        }

    def verify_smtp_connection(self):
        """Test SMTP connection and return detailed status"""
        try:
            self.logger.info("Verifying SMTP connection...")
            if not all([self.smtp_config['username'], self.smtp_config['password']]):
                return False, "SMTP credentials not configured"

            with smtplib.SMTP(self.smtp_config['server'], self.smtp_config['port']) as server:
                server.starttls()
                server.login(self.smtp_config['username'], self.smtp_config['password'])
                self.logger.info("SMTP connection verified successfully")
                return True, "SMTP connection successful"

        except smtplib.SMTPAuthenticationError as e:
            error_msg = "SMTP authentication failed. Please check credentials."
            self.logger.error(f"{error_msg} Details: {str(e)}")
            return False, error_msg
        except smtplib.SMTPConnectError as e:
            error_msg = f"Failed to connect to SMTP server {self.smtp_config['server']}:{self.smtp_config['port']}"
            self.logger.error(f"{error_msg} Details: {str(e)}")
            return False, error_msg
        except Exception as e:
            error_msg = f"SMTP verification failed: {str(e)}"
            self.logger.error(error_msg)
            return False, error_msg

    def get_trend_arrow(self, change):
        """Return trend arrow based on change percentage"""
        if abs(change) < 1:
            return "→"
        return "↑" if change > 0 else "↓"

    def get_status_emoji(self, status):
        """Return status emoji based on status"""
        return "🟢" if status == 'good' else "🟡" if status == 'warning' else "🔴"

    def generate_executive_summary(self, current_metrics, historical_data):
        """Generate executive summary with trends and recommendations"""
        quality_score = self.analyzer.calculate_quality_score(current_metrics)
        metric_status = self.analyzer.get_metric_status(current_metrics)
        
        # Calculate week-over-week changes
        weekly_changes = {}
        monthly_changes = {}
        for metric in current_metrics.keys():
            weekly_comp = self.analyzer.calculate_period_comparison(historical_data, metric, days=7)
            monthly_comp = self.analyzer.calculate_period_comparison(historical_data, metric, days=30)
            if weekly_comp:
                weekly_changes[metric] = weekly_comp
            if monthly_comp:
                monthly_changes[metric] = monthly_comp

        # Identify critical changes and areas needing attention
        critical_changes = []
        attention_areas = []
        improvements = []
        
        for metric, status in metric_status.items():
            if status == 'critical':
                attention_areas.append(metric)
            elif status == 'good' and metric in weekly_changes:
                if weekly_changes[metric]['improved']:
                    improvements.append(metric)
            
            if metric in weekly_changes:
                change = weekly_changes[metric]['change_percentage']
                if abs(change) > 10:  # Significant changes (>10%)
                    critical_changes.append(f"{metric}: {change:+.1f}% {self.get_trend_arrow(change)}")

        return {
            'quality_score': quality_score,
            'critical_changes': critical_changes,
            'attention_areas': attention_areas,
            'improvements': improvements,
            'weekly_changes': weekly_changes,
            'monthly_changes': monthly_changes,
            'metric_status': metric_status
        }

    def generate_project_report(self, project_key, report_type='daily'):
        """Generate a report for a specific project"""
        self.logger.info(f"Starting {report_type} report generation for project: {project_key}")
        try:
            # Fetch current metrics
            metrics = self.sonar_api.get_project_metrics(project_key)
            if not metrics:
                self.logger.error(f"No metrics found for project {project_key}")
                return None, "No metrics found for project"

            metrics_dict = {m['metric']: float(m['value']) for m in metrics}
            self.logger.info("Successfully fetched current metrics")
            
            # Get historical data
            historical_data = self.metrics_processor.get_historical_data(project_key)
            if not historical_data:
                self.logger.warning("No historical data available")
            
            # Generate executive summary
            summary = self.generate_executive_summary(metrics_dict, historical_data)
            self.logger.info("Executive summary generated successfully")
            
            # Prepare report data
            report_data = {
                'timestamp': datetime.now(),
                'project_key': project_key,
                'quality_score': summary['quality_score'],
                'metrics': metrics_dict,
                'status': summary['metric_status'],
                'executive_summary': summary
            }

            self.logger.info(f"Report generation completed for project: {project_key}")
            return report_data, "Report generated successfully"
            
        except Exception as e:
            error_msg = f"Error generating report: {str(e)}"
            self.logger.error(error_msg)
            return None, error_msg

    def format_report_email(self, report_data):
        """Format report data into an HTML email body"""
        self.logger.info("Generating HTML email content")
        try:
            summary = report_data['executive_summary']
            
            html = f"""
            <html>
                <head>
                    <style>
                        .summary-card {{ background: #f5f5f5; padding: 15px; margin: 10px 0; border-radius: 5px; }}
                        .metric-category {{ margin: 20px 0; }}
                        .trend-positive {{ color: green; }}
                        .trend-negative {{ color: red; }}
                        .trend-neutral {{ color: gray; }}
                        table {{ border-collapse: collapse; width: 100%; }}
                        th, td {{ padding: 8px; text-align: left; border-bottom: 1px solid #ddd; }}
                    </style>
                </head>
                <body>
                    <h1>SonarCloud Metrics Executive Report</h1>
                    <p>Generated on: {report_data['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}</p>
                    <p>Project: {report_data['project_key']}</p>

                    <div class="summary-card">
                        <h2>Executive Summary</h2>
                        <p><strong>Overall Quality Score: {summary['quality_score']:.1f}/100</strong></p>
                        
                        <h3>Critical Changes (Past Week)</h3>
                        {'<br>'.join(summary['critical_changes']) if summary['critical_changes'] else 'No critical changes'}
                        
                        <h3>Management Insights</h3>
                        <p><strong>🔔 Areas Requiring Immediate Attention:</strong><br>
                        {', '.join(summary['attention_areas']) if summary['attention_areas'] else 'No immediate attention required'}</p>
                        
                        <p><strong>✨ Recent Improvements:</strong><br>
                        {', '.join(summary['improvements']) if summary['improvements'] else 'No recent improvements detected'}</p>
                    </div>

                    <div class="metric-category">
                        <h2>Metrics Overview</h2>
                        <table>
                            <tr>
                                <th>Category</th>
                                <th>Current</th>
                                <th>WoW Change</th>
                                <th>MoM Change</th>
                                <th>Status</th>
                            </tr>
            """

            # Organize metrics by category
            categories = {
                'Code Quality': ['code_smells', 'duplicated_lines_density'],
                'Security': ['vulnerabilities'],
                'Reliability': ['bugs', 'coverage']
            }

            for category, metrics in categories.items():
                for metric in metrics:
                    if metric in report_data['metrics']:
                        current_value = report_data['metrics'][metric]
                        wow_change = summary['weekly_changes'].get(metric, {}).get('change_percentage', 0)
                        mom_change = summary['monthly_changes'].get(metric, {}).get('change_percentage', 0)
                        status = summary['metric_status'].get(metric, 'neutral')
                        
                        trend_wow = self.get_trend_arrow(wow_change)
                        trend_mom = self.get_trend_arrow(mom_change)
                        status_emoji = self.get_status_emoji(status)
                        
                        html += f"""
                            <tr>
                                <td>{category} - {metric.replace('_', ' ').title()}</td>
                                <td>{current_value:.2f}</td>
                                <td>{wow_change:+.1f}% {trend_wow}</td>
                                <td>{mom_change:+.1f}% {trend_mom}</td>
                                <td>{status_emoji}</td>
                            </tr>
                        """

            html += """
                        </table>
                    </div>
                </body>
            </html>
            """
            self.logger.info("HTML email content generated successfully")
            return html

        except Exception as e:
            error_msg = f"Error generating HTML content: {str(e)}"
            self.logger.error(error_msg)
            raise Exception(error_msg)

    def send_report_email(self, report_data, recipients):
        """Send report via email"""
        self.logger.info(f"Preparing to send report email to: {', '.join(recipients)}")
        try:
            # Verify SMTP connection first
            smtp_status, smtp_message = self.verify_smtp_connection()
            if not smtp_status:
                return False, smtp_message

            # Generate email content
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f"SonarCloud Executive Metrics Report - {report_data['project_key']}"
            msg['From'] = self.smtp_config['username']
            msg['To'] = ', '.join(recipients)

            # Add HTML content
            html_content = self.format_report_email(report_data)
            msg.attach(MIMEText(html_content, 'html'))

            # Generate and attach CSV report
            df = pd.DataFrame([report_data['metrics']])
            csv_data = df.to_csv(index=False)
            csv_attachment = MIMEApplication(csv_data, _subtype='csv')
            csv_attachment.add_header('Content-Disposition', 'attachment', filename='metrics_report.csv')
            msg.attach(csv_attachment)

            # Send email
            with smtplib.SMTP(self.smtp_config['server'], self.smtp_config['port']) as server:
                server.starttls()
                server.login(self.smtp_config['username'], self.smtp_config['password'])
                server.send_message(msg)

            success_msg = f"Report email sent successfully to {', '.join(recipients)}"
            self.logger.info(success_msg)
            return True, success_msg

        except Exception as e:
            error_msg = f"Error sending email: {str(e)}"
            self.logger.error(error_msg)
            return False, error_msg

    def send_email_notification(self, subject, html_content, recipients):
        """Send notification email"""
        self.logger.info(f"Preparing to send notification email to: {', '.join(recipients)}")
        try:
            # Verify SMTP connection first
            smtp_status, smtp_message = self.verify_smtp_connection()
            if not smtp_status:
                return False, smtp_message

            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.smtp_config['username']
            msg['To'] = ', '.join(recipients)

            # Add HTML content
            msg.attach(MIMEText(html_content, 'html'))

            # Send email
            with smtplib.SMTP(self.smtp_config['server'], self.smtp_config['port']) as server:
                server.starttls()
                server.login(self.smtp_config['username'], self.smtp_config['password'])
                server.send_message(msg)

            success_msg = f"Notification email sent successfully to {', '.join(recipients)}"
            self.logger.info(success_msg)
            return True, success_msg

        except Exception as e:
            error_msg = f"Error sending notification email: {str(e)}"
            self.logger.error(error_msg)
            return False, error_msg
