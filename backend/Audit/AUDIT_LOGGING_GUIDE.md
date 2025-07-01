# Enhanced Audit Logging Features

This document describes the comprehensive audit logging system that has been added to the IRS 2290 application for improved monitoring, security, and compliance.

## Overview

The enhanced audit logging system now tracks the following activities:
- User authentication (login/logout attempts)
- Form submissions and document generation
- File downloads and document access
- Account settings changes
- Administrative actions
- API usage and performance monitoring
- Security events and error tracking

## Log Types

### 1. LOGIN_ATTEMPT
Tracks user authentication events
```
2025-07-01 10:30:15,123 - LOGIN_ATTEMPT: SUCCESS | USER: user@example.com | ENV: local | IP: 192.168.1.100
2025-07-01 10:30:45,456 - LOGIN_ATTEMPT: FAILED | USER: hacker@evil.com | ENV: local | IP: 192.168.1.200 | REASON: Invalid credentials
```

### 2. LOGOUT
Tracks user logout events
```
2025-07-01 15:30:15,789 - LOGOUT: USER: user@example.com | ENV: local | IP: 192.168.1.100
```

### 3. FORM_SUBMISSION
Tracks IRS Form 2290 submissions
```
2025-07-01 11:15:30,654 - FORM_SUBMISSION: USER: user@example.com | EIN: 12-3456789 | MONTH: 202507 | VEHICLES: 5 | ENV: local | SUBMISSION_ID: 101
```

### 4. DOCUMENT_ACCESS
Tracks file downloads, views, and deletions
```
2025-07-01 11:20:15,987 - DOCUMENT_ACCESS: DOWNLOAD | USER: user@example.com | TYPE: PDF | ENV: local | DOC_ID: 101 | EIN: 12-3456789
2025-07-01 14:45:30,321 - DOCUMENT_ACCESS: DELETE | USER: admin@send2290.com | TYPE: XML | ENV: local | DOC_ID: 102 | EIN: 98-7654321
```

### 5. SETTINGS_CHANGE
Tracks account and profile changes
```
2025-07-01 12:30:45,159 - SETTINGS_CHANGE: business_name | USER: user@example.com | ENV: local | IP: 192.168.1.100
```

### 6. DATA_ACCESS
Tracks database queries and list views
```
2025-07-01 13:15:20,753 - DATA_ACCESS: VIEW_LIST | USER: admin@send2290.com | TYPE: SUBMISSIONS | ENV: local | RECORDS: 25
2025-07-01 13:20:10,486 - DATA_ACCESS: VIEW_USER_SUBMISSIONS | USER: user@example.com | TYPE: USER_SUBMISSIONS | ENV: local | RECORDS: 3
```

### 7. ERROR_EVENT
Tracks application errors and exceptions
```
2025-07-01 11:45:30,852 - ERROR_EVENT: VALIDATION_ERROR | USER: user@example.com | ENV: local | MSG: Invalid EIN format | ENDPOINT: /build-xml
2025-07-01 12:10:15,741 - ERROR_EVENT: FILE_NOT_FOUND | USER: user@example.com | ENV: local | MSG: XML file not generated yet | ENDPOINT: /download-xml
```

### 8. SECURITY_EVENT
Tracks security-related incidents
```
2025-07-01 09:30:15,963 - SECURITY_EVENT: BRUTE_FORCE_ATTEMPT | ENV: local | IP: 192.168.1.200 | USER: hacker@evil.com | DETAILS: 5 failed login attempts in 2 minutes
2025-07-01 10:15:45,741 - SECURITY_EVENT: UNAUTHORIZED_ADMIN_ACCESS | ENV: local | IP: 192.168.1.150 | USER: user@example.com | DETAILS: Non-admin user attempted admin access
```

### 9. API_USAGE
Tracks API endpoint usage and performance
```
2025-07-01 11:30:20,456 - API_USAGE: POST /build-xml | USER: user@example.com | STATUS: 200 | ENV: local | TIME: 1250ms
2025-07-01 13:45:15,789 - API_USAGE: GET /admin/submissions | USER: admin@send2290.com | STATUS: 200 | ENV: local | TIME: 450ms
```

### 10. ADMIN_ACTION
Tracks administrative operations (legacy format maintained)
```
2025-07-01 14:30:15,321 - ADMIN_ACTION: VIEW_ALL_SUBMISSIONS | USER: admin@send2290.com | ENV: local | DETAILS: Retrieved 25 submissions
2025-07-01 15:15:30,654 - ADMIN_ACTION: DELETE_SUBMISSION_ATTEMPT | USER: admin@send2290.com | ENV: local | DETAILS: Attempting to delete submission ID: 101
```

## Key Features

### 1. IP Address Tracking
All log entries include the client's IP address for security monitoring and forensic analysis.

### 2. User Agent Logging
For security events and settings changes, the user's browser/client information is captured.

### 3. Response Time Monitoring
API usage logs include response time measurements to help identify performance issues.

### 4. EIN Privacy Protection
While EINs are logged for audit purposes, sensitive data like passwords are never logged in plain text.

### 5. Environment Separation
All logs clearly indicate whether they're from 'local' or 'production' environments.

### 6. Error Context
Error logs include endpoint information and detailed error messages for debugging.

## File Locations

- **Local Environment**: `backend/Audit/localaudit.log`
- **Production Environment**: `backend/Audit/productionaudit.log`

## Log Analysis

### Common Queries for Log Analysis

1. **Find all login attempts for a user:**
   ```bash
   grep "LOGIN_ATTEMPT.*user@example.com" localaudit.log
   ```

2. **Find all failed login attempts:**
   ```bash
   grep "LOGIN_ATTEMPT: FAILED" localaudit.log
   ```

3. **Find all form submissions:**
   ```bash
   grep "FORM_SUBMISSION" localaudit.log
   ```

4. **Find all admin actions:**
   ```bash
   grep "ADMIN_ACTION\|SECURITY_EVENT.*ADMIN" localaudit.log
   ```

5. **Find all document downloads:**
   ```bash
   grep "DOCUMENT_ACCESS: DOWNLOAD" localaudit.log
   ```

6. **Find all security events:**
   ```bash
   grep "SECURITY_EVENT" localaudit.log
   ```

7. **Find all errors:**
   ```bash
   grep "ERROR_EVENT" localaudit.log
   ```

8. **Find slow API calls (>1000ms):**
   ```bash
   grep "TIME: [0-9][0-9][0-9][0-9]ms\|TIME: [0-9][0-9][0-9][0-9][0-9]ms" localaudit.log
   ```

## Compliance and Security

This enhanced logging system supports:

1. **IRS Compliance**: Comprehensive audit trail for all taxpayer data access
2. **Security Monitoring**: Real-time detection of suspicious activities
3. **Performance Monitoring**: API response time tracking
4. **Error Tracking**: Detailed error logging for debugging
5. **User Activity Tracking**: Complete user session monitoring

## Testing

To test the logging system, run:
```bash
cd backend
python test_audit_logging.py
```

This will generate sample log entries demonstrating all the new logging features.

## Integration Points

The enhanced logging is automatically integrated into:

1. **Authentication Decorators**: `verify_firebase_token()` and `verify_admin_token()`
2. **Form Submission Endpoints**: `/build-xml`
3. **Document Download Endpoints**: `/download-xml`, `/user/submissions/<id>/download/<type>`
4. **Admin Endpoints**: `/admin/submissions`, `/admin/submissions/<id>` (DELETE)
5. **User Data Endpoints**: `/user/submissions`
6. **API Middleware**: All API requests are logged with response times

## Future Enhancements

Potential future improvements:
1. Log rotation and archiving
2. Real-time log monitoring dashboards
3. Automated security alert system
4. Log aggregation for production environments
5. Integration with external SIEM systems
