# Security Policy

## Supported Versions

We release patches for security vulnerabilities for the following versions:

| Version | Supported          |
| ------- | ------------------ |
| 1.2.x   | :white_check_mark: |
| 1.1.x   | :white_check_mark: |
| < 1.1   | :x:                |

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
