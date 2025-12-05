# Security Policy

## Supported Versions

We release patches for security vulnerabilities for the following versions:

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Reporting a Vulnerability

We take the security of CHORM seriously. If you believe you have found a security vulnerability, please report it to us as described below.

### Please do NOT:

- Open a public GitHub issue for security vulnerabilities
- Disclose the vulnerability publicly before it has been addressed

### Please DO:

1. **Email us directly** at: zwickvitaly@gmail.com
2. **Include the following information**:
   - Type of vulnerability (e.g., SQL injection, authentication bypass, etc.)
   - Full paths of source file(s) related to the vulnerability
   - Location of the affected source code (tag/branch/commit or direct URL)
   - Step-by-step instructions to reproduce the issue
   - Proof-of-concept or exploit code (if possible)
   - Impact of the vulnerability, including how an attacker might exploit it

### What to expect:

- **Acknowledgment**: We will acknowledge receipt of your vulnerability report within 48 hours
- **Communication**: We will keep you informed about the progress of fixing the vulnerability
- **Timeline**: We aim to release a fix within 30 days of the initial report
- **Credit**: We will credit you in the security advisory (unless you prefer to remain anonymous)

## Security Update Process

1. The vulnerability is received and assigned to a primary handler
2. The problem is confirmed and a list of affected versions is determined
3. Code is audited to find any similar problems
4. Fixes are prepared for all supported versions
5. New versions are released and security advisory is published

## Security Best Practices for Users

When using CHORM in production:

1. **Keep CHORM updated** to the latest version
2. **Use parameterized queries** - CHORM handles this automatically, but avoid raw SQL when possible
3. **Validate user input** before passing to database queries
4. **Use environment variables** for database credentials, never hardcode them
5. **Enable SSL/TLS** for database connections in production
6. **Limit database user permissions** - use principle of least privilege
7. **Monitor database access** and set up alerts for suspicious activity
8. **Regular security audits** of your application code

## Known Security Considerations

### SQL Injection

CHORM uses parameterized queries by default, which protects against SQL injection. However:

- Be cautious when using raw SQL strings
- Always validate and sanitize user input
- Use CHORM's query builder instead of string concatenation

### Connection Security

- Always use SSL/TLS in production environments
- Store credentials securely (environment variables, secret managers)
- Rotate database credentials regularly

### Dependency Security

We regularly update our dependencies to address known vulnerabilities. You can check for updates:

```bash
pip list --outdated
```

## Security Disclosure Policy

We follow responsible disclosure principles:

1. Security issues are handled privately until a fix is available
2. We coordinate with affected parties before public disclosure
3. We publish security advisories on GitHub Security Advisories
4. We credit researchers who report vulnerabilities (with permission)

## Contact

For security-related questions or concerns, please contact:

- **Email**: zwickvitaly@gmail.com
- **GitHub**: [@ZwickVitaly](https://github.com/ZwickVitaly)

Thank you for helping keep CHORM and its users safe!
