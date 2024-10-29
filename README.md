# SonarCloud Metrics Dashboard 📊

A comprehensive Streamlit application for monitoring, analyzing, and visualizing SonarCloud metrics with historical data preservation and automated reporting capabilities.

## 🌟 Features

### Core Functionality
- Real-time SonarCloud metrics monitoring
- Historical data tracking and visualization
- Multi-project comparative analysis
- Executive-friendly dashboard interface
- Dark mode optimized visualizations

### Advanced Features
- Automated daily and weekly reports
- Email notifications for significant metric changes
- Project existence tracking
- Inactive project management
- Custom metric calculations
- Trend analysis with moving averages

## 🏗️ Technical Architecture

### Technology Stack
- **Frontend**: Streamlit
- **Database**: PostgreSQL
- **APIs**: SonarCloud REST API
- **Visualization**: Plotly
- **Scheduling**: APScheduler
- **Email**: SMTP Integration

### Component Structure
```
├── components/          # UI Components
├── services/           # Business Logic
├── database/          # Database Operations
├── utils/             # Helper Functions
├── docs/             # Documentation
└── static/           # Static Assets
```

## 🚀 Installation and Setup

### Prerequisites
- Python 3.10+
- PostgreSQL database
- SMTP server access
- SonarCloud API token

### Environment Variables
Required environment variables:
```
SONARCLOUD_TOKEN=your_sonarcloud_token
DATABASE_URL=your_postgresql_url
PGDATABASE=database_name
PGUSER=database_user
PGPASSWORD=database_password
PGHOST=database_host
PGPORT=database_port
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your_email
SMTP_PASSWORD=your_email_password
```

### Installation Steps
1. Clone the repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Set up environment variables
4. Initialize the database:
   ```bash
   python -c "from database.schema import initialize_database; initialize_database()"
   ```
5. Run the application:
   ```bash
   streamlit run main.py
   ```

## 📚 Documentation

### User Guide
- [Detailed User Manual](docs/user_manual.md)
- [Data Usage Policies](docs/data_policies.md)

### Technical Documentation

#### Database Schema
- `repositories`: Project metadata and tracking information
- `metrics`: Historical metric data
- `policy_acceptance`: User policy acceptance tracking

#### API Integration
The application integrates with SonarCloud's REST API to fetch:
- Project metrics
- Quality gates
- Issue statistics
- Coverage data

#### Automated Features
1. **Daily Reports** (1:00 AM)
   - Current metrics summary
   - 24-hour changes
   - Status indicators

2. **Weekly Reports** (Monday 2:00 AM)
   - Week-over-week comparison
   - Trend analysis
   - Executive summary

3. **Change Notifications** (Every 4 hours)
   - Significant metric changes
   - Configurable thresholds
   - HTML formatted alerts

#### Quality Score Calculation
Quality scores (0-100) are calculated based on:
- Code coverage (weight: 2)
- Bugs (weight: -2)
- Vulnerabilities (weight: -3)
- Code smells (weight: -1)
- Duplication (weight: -1)

## 🔒 Security

### Data Privacy
- No source code is collected or stored
- Only numerical metrics and statistics are preserved
- Secure API token handling
- Encrypted data transmission

### Access Control
- Token-based authentication
- Policy acceptance requirement
- Secure SMTP integration
- Database access restrictions

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🔧 Support

For support:
1. Check the [User Manual](docs/user_manual.md)
2. Review the [Data Policies](docs/data_policies.md)
3. Open an issue in the repository
4. Contact the system administrator

## 🙏 Acknowledgments

- SonarCloud for their comprehensive API
- Streamlit for the powerful framework
- The open-source community

---
Built with ❤️ using Streamlit and Python
