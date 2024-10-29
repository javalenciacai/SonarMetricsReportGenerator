# SonarCloud Metrics Dashboard - User Manual 📊

## Table of Contents
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Initial Setup](#initial-setup)
- [Dashboard Navigation](#dashboard-navigation)
  - [Project Selection](#project-selection)
  - [Executive Dashboard](#executive-dashboard)
  - [Trend Analysis](#trend-analysis)
  - [Multi-Project View](#multi-project-view)
- [Features Guide](#features-guide)
  - [Automated Reports](#automated-reports)
  - [Email Notifications](#email-notifications)
  - [Project Management](#project-management)
- [Troubleshooting](#troubleshooting)
- [FAQ](#faq)

## Getting Started

### Prerequisites
Before using the SonarCloud Metrics Dashboard, ensure you have:
1. A SonarCloud account with an API token
2. Access to the projects you want to monitor
3. Email server credentials (for automated reports)

### Initial Setup

#### Step 1: Access the Dashboard
1. Open your web browser and navigate to the dashboard URL
2. The dashboard will prompt you for your SonarCloud token

#### Step 2: Enter SonarCloud Token
1. Go to SonarCloud → User Settings → Security
2. Generate a new token if you don't have one
3. Copy the token
4. Paste it into the dashboard's token input field
5. Click Enter - you should see a success message

## Dashboard Navigation

### Project Selection
The sidebar contains the project selection dropdown with three main options:
- 📊 **All Projects**: Overview of all projects
- ✅ **Active Projects**: Currently analyzed projects
- ⚠️ **Inactive Projects**: Projects no longer found in SonarCloud

### Executive Dashboard
The main dashboard displays:

#### Quality Overview
- Overall Quality Score (0-100)
- Status indicators:
  - 🟢 Good
  - 🟡 Warning
  - 🔴 Critical

#### Key Metrics
1. **Project Size & Debt**
   - Lines of Code (📏)
   - Technical Debt (⏱️)

2. **Security & Reliability**
   - Bugs (🐛)
   - Vulnerabilities (⚠️)

3. **Code Quality**
   - Code Smells (🔧)
   - Test Coverage (📊)
   - Code Duplication (📝)

### Trend Analysis
Access detailed trends through the "Trend Analysis" tab:

1. **Historical Charts**
   - Lines of Code trend
   - Technical Debt progression
   - Issues tracking
   - Quality metrics evolution

2. **Comparative Analysis**
   - Week-over-week changes
   - Month-over-month trends
   - Moving averages (7-day, 30-day)

### Multi-Project View
The "All Projects" view provides:
1. Organization Totals
   - Total Lines of Code
   - Aggregate Technical Debt

2. Project Rankings
   - Quality Score sorting
   - Metric comparisons
   - Status indicators

## Features Guide

### Automated Reports

#### Setting Up Reports
1. Select a project from the sidebar
2. Navigate to "Automation Setup"
3. Enter email recipient(s) separated by commas
4. Click "Setup Automation"

#### Report Types
1. **Daily Reports** (1:00 AM)
   - Current metrics
   - 24-hour changes
   - Critical issues

2. **Weekly Reports** (Monday 2:00 AM)
   - Week-over-week comparison
   - Trend analysis
   - Executive summary

### Email Notifications

#### Configuration
1. Verify email settings in the sidebar
2. Look for "✉️ Email Configuration: Connected"
3. If not connected, check SMTP credentials

#### Notification Types
1. **Metric Change Alerts**
   - Significant metric changes
   - Every 4 hours
   - Customizable thresholds

2. **Status Updates**
   - Quality score changes
   - New critical issues
   - Coverage drops

### Project Management

#### Active Projects
- Indicated by ✅
- Real-time metric updates
- Full feature access

#### Inactive Projects
1. **Identification**
   - Marked with ⚠️
   - Last seen date displayed
   - Inactive duration shown

2. **Management Options**
   - View historical data
   - Mark for deletion
   - Remove deletion mark
   - Permanent deletion

## Troubleshooting

### Common Issues

1. **Token Invalid**
   - Verify token permissions
   - Check token expiration
   - Generate a new token if needed

2. **Email Configuration**
   - Confirm SMTP credentials
   - Check recipient email format
   - Verify server connectivity

3. **Data Not Updating**
   - Check project existence in SonarCloud
   - Verify analysis completion
   - Review project permissions

### Error Messages

1. **"No metrics found for project"**
   - Ensure project is analyzed in SonarCloud
   - Check project permissions
   - Wait for analysis completion

2. **"Email Configuration Error"**
   - Verify SMTP credentials
   - Check network connectivity
   - Confirm email server status

## FAQ

**Q: How often are metrics updated?**
A: Metrics are fetched in real-time when viewing a project. Historical data is preserved for trend analysis.

**Q: Can I track deleted projects?**
A: Yes, inactive projects remain visible with their historical data until manually deleted.

**Q: How are quality scores calculated?**
A: Quality scores (0-100) consider:
- Code coverage (weight: 2)
- Bugs (weight: -2)
- Vulnerabilities (weight: -3)
- Code smells (weight: -1)
- Duplication (weight: -1)

**Q: What do the status indicators mean?**
- 🟢 Good: Metric within acceptable range
- 🟡 Warning: Metric approaching threshold
- 🔴 Critical: Metric exceeded threshold

**Q: Can I customize notification thresholds?**
A: The system uses predefined thresholds:
- Bugs: 20% increase
- Vulnerabilities: 20% increase
- Code Smells: 25% increase
- Coverage: 10% decrease
- Duplication: 30% increase
