# Security Policy

## 🚨 URGENT: Critical Security Update v1.3.8

**Release Date**: December 20, 2025
**Severity**: CRITICAL
**CVSS Score**: 9.8
**Status**: FIXED in v1.3.8

### Overview

Multiple **Remote Code Execution (RCE)** vulnerabilities have been identified and fixed in Depl0y v1.3.8. These vulnerabilities could allow attackers to execute arbitrary commands on the server through unsanitized input in various API endpoints.

**⚠️ ALL USERS MUST UPDATE IMMEDIATELY TO v1.3.8 OR LATER ⚠️**

### Fixed Vulnerabilities (v1.3.8)

#### 1. Command Injection in Setup API (CRITICAL)
- **Component**: `backend/app/api/setup.py`
- **CVSS**: 9.8 (Critical)
- **Description**: Unsanitized hostname and node name inputs passed directly to shell commands via `subprocess.run(..., shell=True)`, allowing arbitrary command execution.
- **Attack Vector**: Network, potentially unauthenticated during setup phase
- **Fixed in**: Commit 3786c83
- **Mitigation Applied**:
  - Added regex validation for hostnames and node names (`^[a-zA-Z0-9._-]+$`)
  - Replaced all `shell=True` calls with safe argument lists
  - Implemented `shlex.quote()` for proper shell escaping

#### 2. Command Injection in System Updates API (CRITICAL)
- **Component**: `backend/app/api/system_updates.py`
- **CVSS**: 9.8 (Critical)
- **Description**: Unsafe subprocess execution with `shell=True` in update package creation and installer execution.
- **Attack Vector**: Network, requires admin authentication
- **Fixed in**: Commit 3786c83
- **Mitigation Applied**:
  - Replaced `shell=True` with safe argument-based subprocess calls
  - Added path validation with regex for installer paths

#### 3. Sensitive Data Exposure in Logs (HIGH)
- **Component**: `backend/app/api/vms.py`
- **CVSS**: 7.5 (High)
- **Description**: VM creation endpoint logs passwords and SSH keys in plaintext, exposing credentials in log files.
- **Attack Vector**: Local, requires log file access
- **Fixed in**: Commit 3786c83
- **Mitigation Applied**:
  - Redact passwords and SSH keys from all log output
  - Implemented password encryption before database storage

#### 4. Weak Cryptographic Key (HIGH)
- **Component**: `backend/app/core/config.py`
- **CVSS**: 7.5 (High)
- **Description**: Default weak SECRET_KEY used for JWT token signing if environment variable not set.
- **Attack Vector**: Network, allows JWT forgery
- **Fixed in**: Commit 3786c83
- **Mitigation Applied**:
  - Auto-generate cryptographically strong 64-byte random SECRET_KEY using `secrets.token_urlsafe(64)`

#### 5. Multiple Command Injection Vectors in Deployment Service (CRITICAL)
- **Component**: `backend/app/services/deployment.py`
- **CVSS**: 9.8 (Critical)
- **Description**: Multiple unsanitized inputs (hostname, node names, VMIDs, IP addresses) passed to SSH commands via `shell=True`.
- **Attack Vector**: Network, requires authenticated API access
- **Fixed in**: Commit 3786c83
- **Mitigation Applied**:
  - Comprehensive input validation for all parameters
  - Replaced all `shell=True` subprocess calls with safe argument lists
  - Added timeout protection on all subprocess calls

### Immediate Update Instructions

```bash
# Navigate to installation directory
cd /opt/depl0y

# Pull latest security fixes
git pull origin main

# Verify you're on v1.3.8 or later
git describe --tags

# Should output: v1.3.8 or later

# Restart backend service
sudo systemctl restart depl0y-backend

# Verify service is running
sudo systemctl status depl0y-backend
```

### Security Improvements in v1.3.8

- ✅ **Input Validation**: Strict regex validation on all user-provided inputs
- ✅ **No Shell Injection**: All `shell=True` subprocess calls eliminated
- ✅ **Proper Escaping**: `shlex.quote()` used for all dynamic shell parameters
- ✅ **Secrets Management**: Strong cryptographic key generation
- ✅ **Sensitive Data Protection**: Credentials redacted from logs and encrypted in database
- ✅ **Timeout Protection**: All subprocess calls have timeout limits

### References

- [OWASP Command Injection](https://owasp.org/www-community/attacks/Command_Injection)
- [CWE-78: OS Command Injection](https://cwe.mitre.org/data/definitions/78.html)
- Commit: https://github.com/agit8or1/Depl0y/commit/3786c83

---

## Supported Versions

We release patches for security vulnerabilities for the following versions:

| Version | Supported          | Security Status          |
| ------- | ------------------ | ------------------------ |
| 1.3.8+  | :white_check_mark: | Secure                   |
| 1.3.7   | :warning:          | **CRITICAL RCE - UPDATE IMMEDIATELY** |
| 1.3.6   | :warning:          | **CRITICAL RCE - UPDATE IMMEDIATELY** |
| 1.2.x   | :x:                | **CRITICAL RCE - UPDATE IMMEDIATELY** |
| 1.1.x   | :x:                | **CRITICAL RCE - UPDATE IMMEDIATELY** |
| < 1.1   | :x:                | **CRITICAL RCE - UPDATE IMMEDIATELY** |

**⚠️ All versions prior to 1.3.8 contain critical RCE vulnerabilities and must be upgraded immediately.**

## Reporting a Vulnerability

**Please do not report security vulnerabilities through public GitHub issues.**

Instead, please report them via email to **agit8or@agit8or.net** with the subject line "Depl0y Security Vulnerability".

You should receive a response within 48 hours. If for some reason you do not, please follow up via email to ensure we received your original message.

Please include the following information:

- Type of issue (e.g. buffer overflow, SQL injection, cross-site scripting, etc.)
- Full paths of source file(s) related to the manifestation of the issue
- The location of the affected source code (tag/branch/commit or direct URL)
- Any special configuration required to reproduce the issue
- Step-by-step instructions to reproduce the issue
- Proof-of-concept or exploit code (if possible)
- Impact of the issue, including how an attacker might exploit it

## Disclosure Policy

When we receive a security bug report, we will:

1. Confirm the problem and determine the affected versions
2. Audit code to find any similar problems
3. Prepare fixes for all supported releases
4. Release patched versions as soon as possible

## Security Best Practices

When deploying Depl0y in production:

### Authentication
- Change the default admin password immediately after installation
- Enable 2FA (TOTP) for all admin accounts
- Use strong, unique passwords (minimum 12 characters)
- Regularly rotate passwords and API tokens

### Network Security
- Use HTTPS in production (configure SSL/TLS certificates)
- Restrict network access to trusted IPs when possible
- Place Depl0y behind a firewall
- Use a VPN for remote access

### Data Protection
- Regularly backup your database
- Encrypt sensitive data at rest
- Use encrypted connections to Proxmox hosts
- Store encryption keys securely

### System Hardening
- Keep Depl0y updated to the latest version
- Regularly update the host operating system
- Regularly update Proxmox VE to the latest stable version
- Monitor system logs for suspicious activity
- Disable unused features and services

### Access Control
- Follow the principle of least privilege
- Use role-based access control (Admin, Operator, Viewer)
- Regularly audit user accounts and permissions
- Remove inactive user accounts promptly

### Proxmox Integration
- Use API tokens instead of passwords when possible
- Create dedicated users for Depl0y in Proxmox
- Limit permissions to only what's needed
- Enable Proxmox audit logging

### Database Security
- Use strong database passwords
- Restrict database access to localhost when possible
- Regularly backup the database
- Keep SQLite updated

### Updates
- Use the built-in update mechanism from Settings
- Test updates in a non-production environment first
- Review release notes before applying updates
- Subscribe to release notifications on GitHub

## Known Security Considerations

### Credential Storage
- Proxmox credentials are encrypted using Fernet symmetric encryption
- Encryption key must be kept secure and backed up
- Loss of encryption key means loss of stored credentials

### API Security
- API uses JWT tokens for authentication
- Tokens expire after 30 minutes by default
- Refresh tokens expire after 7 days
- Configure appropriate token lifetimes for your security needs

### File Uploads
- ISO and cloud image uploads are restricted to specific directories
- File size limits are enforced
- File types are validated
- Malicious files should be prevented, but additional scanning is recommended

## Security Updates

Subscribe to releases on GitHub to receive notifications about security updates:
https://github.com/agit8or1/Depl0y/releases

## Comments on this Policy

If you have suggestions on how this process could be improved, please submit a pull request or open an issue.
