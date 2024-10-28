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

    def generate_project_report(self, project_key, report_type='daily'):
        """Generate a report for a specific project"""
        try:
            # Fetch current metrics
            metrics = self.sonar_api.get_project_metrics(project_key)
            if not metrics:
                self.logger.error(f"No metrics found for project {project_key}")
                return None

            metrics_dict = {m['metric']: float(m['value']) for m in metrics}
            
            # Get historical data
            historical_data = self.metrics_processor.get_historical_data(project_key)
            
            # Calculate quality score and trends
            quality_score = self.analyzer.calculate_quality_score(metrics_dict)
            metric_status = self.analyzer.get_metric_status(metrics_dict)
            
            # Prepare report data
            report_data = {
                'timestamp': datetime.now(),
                'project_key': project_key,
                'quality_score': quality_score,
                'metrics': metrics_dict,
                'status': metric_status
            }

            # Add trend analysis for weekly reports
            if report_type == 'weekly':
                for metric in metrics_dict.keys():
                    trend_data = self.analyzer.calculate_trend(historical_data, metric)
                    period_comparison = self.analyzer.calculate_period_comparison(historical_data, metric)
                    if trend_data and period_comparison:
                        report_data[f'{metric}_trend'] = trend_data
                        report_data[f'{metric}_comparison'] = period_comparison

            return report_data
            
        except Exception as e:
            self.logger.error(f"Error generating report: {str(e)}")
            return None

    def format_report_email(self, report_data):
        """Format report data into an email body"""
        html = f"""
        <html>
            <body>
                <h2>SonarCloud Metrics Report</h2>
                <p>Generated on: {report_data['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}</p>
                <p>Project: {report_data['project_key']}</p>
                <h3>Quality Score: {report_data['quality_score']:.1f}/100</h3>
                
                <h3>Current Metrics:</h3>
                <table border="1">
                    <tr><th>Metric</th><th>Value</th><th>Status</th></tr>
        """
        
        for metric, value in report_data['metrics'].items():
            status = report_data['status'].get(metric, 'N/A')
            status_emoji = "🟢" if status == 'good' else "🟡" if status == 'warning' else "🔴"
            html += f"<tr><td>{metric}</td><td>{value}</td><td>{status_emoji}</td></tr>"
        
        html += """
                </table>
            </body>
        </html>
        """
        return html

    def send_report_email(self, report_data, recipients):
        """Send report via email"""
        try:
            smtp_server = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
            smtp_port = int(os.getenv('SMTP_PORT', '587'))
            smtp_username = os.getenv('SMTP_USERNAME')
            smtp_password = os.getenv('SMTP_PASSWORD')

            if not all([smtp_username, smtp_password]):
                self.logger.error("SMTP credentials not configured")
                return False

            msg = MIMEMultipart('alternative')
            msg['Subject'] = f"SonarCloud Metrics Report - {report_data['project_key']}"
            msg['From'] = smtp_username
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
            with smtplib.SMTP(smtp_server, smtp_port) as server:
                server.starttls()
                server.login(smtp_username, smtp_password)
                server.send_message(msg)

            self.logger.info("Report email sent successfully")
            return True

        except Exception as e:
            self.logger.error(f"Error sending email: {str(e)}")
            return False
