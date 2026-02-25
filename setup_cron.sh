#!/bin/bash
# Setup script for EMEA Sales Alert Cron Jobs

echo "Setting up EMEA Sales Alert Cron Jobs..."

# Create cron entries
CRON_JOBS="# EMEA Sales Morning Briefing - Daily at 9:00 CET (8:00 UTC)
0 8 * * * cd /Users/philippsandor/.openclaw/workspace/bitwise/leadtracker && /usr/bin/python3 morning_briefing.py >> /tmp/morning_briefing.log 2>&1
# Sales Stale Check - Every 4 hours
0 */4 * * * cd /Users/philippsandor/.openclaw/workspace/bitwise/leadtracker && /usr/bin/python3 alert_service.py stale >> /tmp/sales_alerts.log 2>&1
"

# Write to crontab
(echo "$CRON_JOBS") | crontab -

echo "Cron jobs installed. Current crontab:"
crontab -l
