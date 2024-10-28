# SonarCloud Metrics Dashboard 📊

A comprehensive Streamlit application that fetches, stores, and visualizes SonarCloud metrics with historical data preservation. This dashboard provides real-time insights into your code quality metrics with executive-friendly visualizations and automated reporting capabilities.

## 🌟 Features

### Real-time Metrics Monitoring
- Live metrics fetching from SonarCloud API
- Interactive visualizations using Plotly
- Dark mode compatible interface
- Executive-friendly layout with clear metrics presentation

### Comprehensive Analytics
- Quality score calculations (0-100 scale)
- Trend analysis with 7-day and 30-day comparisons
- Moving averages for key metrics
- Status indicators (🟢 Good, 🟡 Warning, 🔴 Critical)

### Multi-Project Support
- Compare metrics across multiple projects
- Organization-wide overview
- Project rankings and benchmarking
- Aggregated statistics

### Automated Reporting
- Daily reports (1 AM)
- Weekly executive summaries (Monday 2 AM)
- Email notifications for significant metric changes
- Customizable report recipients

### Historical Data Tracking
- Metric trends over time
- Historical data preservation
- CSV report generation
- Comparative period analysis

## 🚀 Getting Started

### Prerequisites
- Python 3.11 or higher
- PostgreSQL database
- SonarCloud account and API token
- SMTP server for email notifications

### Environment Variables
Configure the following environment variables:
```bash
# Database Configuration
PGDATABASE=your_database
PGUSER=your_user
PGPASSWORD=your_password
PGHOST=your_host
PGPORT=your_port

# SonarCloud Configuration
SONARCLOUD_TOKEN=your_token

# SMTP Configuration
SMTP_SERVER=smtp.gmail.com    # SMTP server address (default: smtp.gmail.com)
SMTP_PORT=587                 # SMTP port (default: 587)
SMTP_USERNAME=your_email
SMTP_PASSWORD=your_password
```

### Installation

1. Clone this repository:
```bash
git clone <repository-url>
cd sonarcloud-metrics-dashboard
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Start the application:
```bash
streamlit run main.py
```

## 📱 Usage Guide

### Initial Setup
1. Launch the application
2. Enter your SonarCloud token when prompted
3. Select a project from the sidebar dropdown
4. Configure email recipients for automated reports

### Dashboard Navigation
- **Executive Dashboard**: Overview of current metrics
- **Trend Analysis**: Historical data and comparisons
- **Multi-Project View**: Compare metrics across projects
- **Download Reports**: Generate and export CSV reports

### Automated Reports Configuration
1. Enter email recipients in the sidebar
2. Click "Setup Automation"
3. Confirm successful setup
4. Reports will be automatically generated and sent:
   - Daily reports at 1:00 AM
   - Weekly reports on Mondays at 2:00 AM
   - Change notifications every 4 hours

## 📊 Metrics Overview

### Core Metrics
- **Bugs**: Number of reliability issues
- **Vulnerabilities**: Security vulnerabilities count
- **Code Smells**: Maintainability issues
- **Coverage**: Test coverage percentage
- **Duplication**: Code duplication percentage
- **Lines of Code**: Project size
- **Technical Debt**: Estimated fix time

### Quality Indicators
- **Quality Score**: Overall project health (0-100)
- **Status Indicators**: 🟢 Good, 🟡 Warning, 🔴 Critical
- **Trend Indicators**: 📈 Increasing, 📉 Decreasing, ➡️ Stable

## 🏗️ Project Structure
```
├── components/             # UI components
│   ├── metrics_display.py  # Metrics visualization components
│   └── visualizations.py   # Plotly charts and graphs
├── database/              # Database operations
│   ├── connection.py      # Database connection handling
│   └── schema.py         # Database schema definitions
├── services/              # Core services
│   ├── metric_analyzer.py # Metric analysis logic
│   ├── sonarcloud.py     # SonarCloud API integration
│   └── report_generator.py# Report generation service
├── utils/                 # Utility functions
├── .streamlit/           # Streamlit configuration
└── main.py               # Application entry point
```

## 📝 Dependencies
- **streamlit**: Web application framework
- **plotly**: Interactive visualizations
- **pandas**: Data manipulation
- **psycopg2**: PostgreSQL database connector
- **requests**: HTTP client for API calls
- **apscheduler**: Task scheduling

## 🤝 Contributing
Contributions are welcome! Please feel free to submit pull requests.

## 📄 License
This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments
- SonarCloud for providing the metrics API
- Streamlit for the excellent web framework
- Plotly for the visualization capabilities
