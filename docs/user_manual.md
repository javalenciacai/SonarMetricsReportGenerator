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
  - [Project Groups](#project-groups)
- [Features Guide](#features-guide)
  - [Automated Reports](#automated-reports)
  - [Email Notifications](#email-notifications)
  - [Project Management](#project-management)
  - [Update Intervals](#update-intervals)
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
- 👥 **Project Groups**: View and manage project groups

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

#### Understanding Trend Analysis
1. **Moving Averages**
   - 7-day moving average (solid line)
   - 30-day moving average (dotted line)
   - Helps smooth out daily fluctuations

2. **Trend Indicators**
   - 📈 Increasing trend
   - 📉 Decreasing trend
   - ➡️ Stable trend

3. **Period Comparisons**
   - Current vs Previous 7-day averages
   - Percentage changes with color coding:
     - 🟢 Green: Positive change
     - 🔴 Red: Negative change
     - ⚪ Gray: No significant change

4. **Metric Interpretation**
   - Lines of Code: Growth indicator
   - Technical Debt: Lower is better
   - Issues (Bugs, Vulnerabilities): Reduction is positive
   - Coverage: Higher is better
   - Duplication: Lower is better

### Multi-Project View
The "All Projects" view provides:
1. Organization Totals
   - Total Lines of Code
   - Aggregate Technical Debt

2. Project Rankings
   - Quality Score sorting
   - Metric comparisons
   - Status indicators

### Project Groups
Manage and analyze multiple projects together:

1. **Group Creation**
   - Create named groups
   - Add project descriptions
   - Set group-wide update intervals

2. **Group Management**
   - Add/remove projects
   - View grouped metrics
   - Compare projects within groups

3. **Group Metrics**
   - Aggregated group statistics
   - Comparative visualizations
   - Trend analysis by group

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

### Update Intervals

#### Setting Update Frequency
1. Navigate to Update Interval Settings
2. Choose from available intervals:
   - 5 minutes
   - 15 minutes
   - 30 minutes
   - 1 hour (default)
   - 2 hours
   - 4 hours
   - 8 hours
   - 12 hours
   - 24 hours

#### Interval Management
1. **Individual Projects**
   - Set per-project update frequency
   - View last update timestamp
   - Modify as needed

2. **Project Groups**
   - Set group-wide update intervals
   - Override individual project settings
   - Optimize resource usage

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
A: Metrics are updated based on your configured interval (5 minutes to 24 hours). Default is 1 hour.

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

**Q: How do I manage inactive projects?**
A: Inactive projects can be:
1. Marked for deletion
2. Kept for historical reference
3. Permanently deleted when needed
4. Unmarked if they become active again

**Q: What's the benefit of project groups?**
A: Project groups allow you to:
1. Organize related projects
2. View aggregated metrics
3. Set common update intervals
4. Compare projects easily
