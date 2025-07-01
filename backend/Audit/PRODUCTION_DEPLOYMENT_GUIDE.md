# Production Deployment Guide for Enhanced Audit Logging

This guide explains how to deploy and configure the enhanced audit logging system in your production environment.

## Production Environment Setup

### 1. Environment Variables

Ensure these environment variables are set in your production environment:

```bash
# Production Environment Indicator
FLASK_ENV=production

# Database (required for production detection)
DATABASE_URL=postgresql://user:password@host:port/database

# AWS Configuration (required for production detection)
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_DEFAULT_REGION=us-east-1
FILES_BUCKET=your-s3-bucket

# Firebase Configuration
FIREBASE_ADMIN_KEY_JSON='{"type": "service_account", ...}'

# Admin Configuration
ADMIN_EMAIL=admin@yourdomain.com
```

### 2. Log Directory Setup

Create the Audit directory structure in your production deployment:

```bash
mkdir -p backend/Audit
chmod 755 backend/Audit
```

### 3. Log File Permissions

Ensure proper permissions for log files:

```bash
touch backend/Audit/productionaudit.log
chmod 644 backend/Audit/productionaudit.log
chown app:app backend/Audit/productionaudit.log  # Replace with your app user
```

### 4. Log Rotation Setup

Configure log rotation to prevent disk space issues:

Create `/etc/logrotate.d/send2290-audit`:

```bash
/path/to/your/app/backend/Audit/productionaudit.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 644 app app
    postrotate
        systemctl reload your-app-service
    endscript
}
```

## AWS Elastic Beanstalk Deployment

### 1. EB Configuration Files

Create `.ebextensions/01-audit-logging.config`:

```yaml
files:
  "/opt/elasticbeanstalk/hooks/appdeploy/post/01_create_audit_dir.sh":
    mode: "000755"
    owner: root
    group: root
    content: |
      #!/bin/bash
      mkdir -p /var/app/current/backend/Audit
      chown webapp:webapp /var/app/current/backend/Audit
      chmod 755 /var/app/current/backend/Audit
      
      touch /var/app/current/backend/Audit/productionaudit.log
      chown webapp:webapp /var/app/current/backend/Audit/productionaudit.log
      chmod 644 /var/app/current/backend/Audit/productionaudit.log

  "/etc/logrotate.d/send2290-audit":
    mode: "000644"
    owner: root
    group: root
    content: |
      /var/app/current/backend/Audit/productionaudit.log {
          daily
          rotate 30
          compress
          delaycompress
          missingok
          notifempty
          create 644 webapp webapp
      }
```

### 2. Environment Configuration

Set environment variables in EB configuration:

```bash
eb setenv FLASK_ENV=production
eb setenv DATABASE_URL=your_production_db_url
eb setenv AWS_ACCESS_KEY_ID=your_key
eb setenv AWS_SECRET_ACCESS_KEY=your_secret
eb setenv FILES_BUCKET=your-bucket
eb setenv FIREBASE_ADMIN_KEY_JSON='your_firebase_config_json'
eb setenv ADMIN_EMAIL=admin@yourdomain.com
```

## Docker Deployment

### 1. Dockerfile Updates

Add to your Dockerfile:

```dockerfile
# Create audit log directory
RUN mkdir -p /app/backend/Audit && \
    chmod 755 /app/backend/Audit

# Create log file with proper permissions
RUN touch /app/backend/Audit/productionaudit.log && \
    chmod 644 /app/backend/Audit/productionaudit.log

# Install logrotate (if needed)
RUN apt-get update && apt-get install -y logrotate
```

### 2. Docker Compose Updates

Add volume mounts for persistent logging:

```yaml
version: '3.8'
services:
  app:
    build: .
    environment:
      - FLASK_ENV=production
      - DATABASE_URL=${DATABASE_URL}
      - AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID}
      - AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY}
      - FILES_BUCKET=${FILES_BUCKET}
      - FIREBASE_ADMIN_KEY_JSON=${FIREBASE_ADMIN_KEY_JSON}
      - ADMIN_EMAIL=${ADMIN_EMAIL}
    volumes:
      - audit_logs:/app/backend/Audit
    ports:
      - "5000:5000"

volumes:
  audit_logs:
```

## Monitoring and Alerting

### 1. Log Monitoring Script

Deploy the production log analyzer as a cron job:

```bash
# Add to crontab for daily reports
0 6 * * * /usr/bin/python3 /path/to/your/app/backend/production_log_analyzer.py > /var/log/daily_audit_report.log 2>&1

# Add for hourly security monitoring
0 * * * * /usr/bin/python3 /path/to/your/app/backend/monitor_security.py
```

### 2. CloudWatch Integration (AWS)

For AWS deployments, integrate with CloudWatch:

Create `.ebextensions/02-cloudwatch-logs.config`:

```yaml
Resources:
  AWSEBAutoScalingGroup:
    Metadata:
      AWS::CloudFormation::Authentication:
        S3Auth:
          type: "s3"
          buckets: ["elasticbeanstalk-*"]
          roleName: 
            "Fn::GetOptionSetting":
              Namespace: "aws:autoscaling:launchconfiguration"
              OptionName: "IamInstanceProfile"
              DefaultValue: "aws-elasticbeanstalk-ec2-role"

files:
  "/opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json":
    mode: "000600"
    owner: root
    group: root
    content: |
      {
        "logs": {
          "logs_collected": {
            "files": {
              "collect_list": [
                {
                  "file_path": "/var/app/current/backend/Audit/productionaudit.log",
                  "log_group_name": "/aws/elasticbeanstalk/send2290/audit",
                  "log_stream_name": "production-audit-{instance_id}"
                }
              ]
            }
          }
        }
      }
```

### 3. Alert Configuration

Set up alerts for critical events:

```python
# Add to your monitoring script
def send_security_alert(event_type, details):
    """Send alert for critical security events"""
    import boto3
    
    sns = boto3.client('sns')
    
    message = f"""
    🚨 SECURITY ALERT: {event_type}
    
    Time: {datetime.now()}
    Environment: Production
    Details: {details}
    
    Please investigate immediately.
    """
    
    sns.publish(
        TopicArn='arn:aws:sns:region:account:security-alerts',
        Message=message,
        Subject=f'Production Security Alert: {event_type}'
    )
```

## Verification Steps

### 1. Test Environment Detection

Deploy and verify environment detection:

```bash
# Check application logs for this message:
# "🔍 Audit Logger Environment: production"

grep "Audit Logger Environment" /var/log/your-app.log
```

### 2. Test Log Generation

Run the production test script:

```bash
python3 backend/test_production_logging.py
```

### 3. Verify Log File Creation

Check that the production log file is created:

```bash
ls -la backend/Audit/productionaudit.log
tail -f backend/Audit/productionaudit.log
```

### 4. Test Log Analysis

Run the log analyzer:

```bash
python3 backend/production_log_analyzer.py
```

## Security Considerations

### 1. Log File Protection

- Set appropriate file permissions (644 for log files, 755 for directories)
- Use proper user/group ownership
- Consider encryption for sensitive log data

### 2. Access Control

- Limit access to audit logs to authorized personnel only
- Implement log tampering detection
- Regular backup of audit logs

### 3. Compliance

- Ensure logs meet IRS compliance requirements
- Maintain appropriate retention policies
- Implement secure log archival

## Troubleshooting

### Common Issues

1. **Log file not created**
   - Check directory permissions
   - Verify environment variables
   - Check application logs for errors

2. **Environment not detected as production**
   - Verify FLASK_ENV=production is set
   - Check DATABASE_URL format
   - Ensure AWS credentials are present

3. **Permission denied errors**
   - Check file/directory ownership
   - Verify write permissions
   - Check SELinux policies (if applicable)

### Debug Commands

```bash
# Check environment variables
env | grep -E "(FLASK_ENV|DATABASE_URL|AWS_)"

# Check log file permissions
ls -la backend/Audit/

# Test logging manually
python3 -c "
from backend.Audit.enhanced_audit import IRS2290AuditLogger
logger = IRS2290AuditLogger('production')
logger.log_security_event('TEST_EVENT', details='Deployment test')
print('Test log entry created')
"
```

## Performance Considerations

- Monitor log file sizes and implement rotation
- Consider asynchronous logging for high-traffic environments
- Use appropriate log levels to avoid excessive disk I/O
- Monitor disk space usage regularly

This enhanced audit logging system provides comprehensive monitoring and compliance capabilities for your production IRS 2290 application.
