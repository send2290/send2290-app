# Audit Folder

This folder contains the audit logging system for the IRS 2290 application.

## Files Overview

### ✅ **Files to Commit (Tracked by Git)**
- `enhanced_audit.py` - Core audit logging system
- `fetch_production_logs.py` - Production log retrieval utility
- `view_audit_logs.py` - Log viewing utility
- `README.md` - This documentation file

### ❌ **Files to NOT Commit (Ignored by Git)**
- `*.log` - All log files contain sensitive user data
- `localaudit.log` - Local development logs
- `productionaudit.log` - Production environment logs

## Security Note

**⚠️ IMPORTANT: Log files contain sensitive information including:**
- User email addresses and UIDs
- Business EINs (Tax Identification Numbers)
- IP addresses and authentication attempts
- Form submission details
- Admin activities and data access patterns

**These files should NEVER be committed to version control for:**
- Privacy protection
- Security compliance
- IRS regulations compliance
- GDPR/data protection requirements

## Log File Structure

### Local Environment
- `localaudit.log` - Created automatically during development
- Used for testing and debugging
- Contains development user activities

### Production Environment
- `productionaudit.log` - Created automatically in production
- Contains real customer data
- Subject to strict data protection requirements
- Should be backed up securely and rotated regularly

## Deployment Notes

When deploying to production:
1. Ensure the Audit directory exists with proper permissions
2. Log files will be created automatically by the application
3. Set up log rotation to prevent disk space issues
4. Configure monitoring and alerting for security events
5. Implement secure backup procedures for compliance

## Related Documentation
- `../AUDIT_LOGGING_GUIDE.md` - Complete logging reference
- `../PRODUCTION_DEPLOYMENT_GUIDE.md` - Production setup instructions
- `../PRODUCTION_IMPLEMENTATION_SUMMARY.md` - Implementation overview
