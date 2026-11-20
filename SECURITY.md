# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| Latest  | :white_check_mark: |

## Reporting a Vulnerability

If you discover a security vulnerability in this project, please report it responsibly.

**Please do NOT open a public GitHub issue for security vulnerabilities.**

### How to Report

1. **Email**: Send details to the maintainer via the email address listed on the [GitHub profile](https://github.com/diaoyunxi)
2. **GitHub Private Vulnerability Reporting**: Use the "Report a vulnerability" button on the [Security Advisories](../../security/advisories) page (if enabled)

### What to Include

- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

### Response Timeline

- **Acknowledgement**: Within 48 hours of receipt
- **Initial Assessment**: Within 7 days
- **Resolution**: Target within 30 days for critical/high severity issues

### Scope

The following are in scope:

- Code in the `main` branch
- Dependencies with known CVEs
- Authentication and authorization bypass
- Data leakage or information disclosure
- Remote code execution
- Denial of service

### Out of Scope

- Issues in third-party dependencies (report to the upstream project)
- Social engineering attacks
- Physical attacks
- Issues requiring physical access to the server

## Security Best Practices for Deployment

1. **Bind to localhost**: Set `HOST=127.0.0.1` unless external access is required
2. **Use API keys**: Set `API_KEY` environment variable for production deployments
3. **Rate limiting**: Configure `MAX_REQUESTS_PER_MINUTE` to prevent abuse
4. **HTTPS**: Use a reverse proxy (Caddy, Nginx) with TLS in production
5. **Firewall**: Restrict network access to the server port
6. **Updates**: Keep dependencies up to date via Dependabot alerts
