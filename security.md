# Security Policy

## Supported Versions

We release patches for security vulnerabilities in the following versions:

| Version | Supported          |
| ------- | ------------------ |
| 0.4.x   | :white_check_mark: |
| < 0.4   | :x:                |

## Reporting a Vulnerability

**Please do not report security vulnerabilities through public GitHub issues.**

Instead, please report them via email to: **security@[yourdomain].com**

You should receive a response within 48 hours. If for some reason you do not, please follow up via email to ensure we received your original message.

### What to Include

To help us better understand and resolve the issue, please include as much of the following information as possible:

- **Type of issue** (e.g., buffer overflow, SQL injection, cross-site scripting, etc.)
- **Full paths of source file(s)** related to the manifestation of the issue
- **Location of the affected source code** (tag/branch/commit or direct URL)
- **Step-by-step instructions** to reproduce the issue
- **Proof-of-concept or exploit code** (if possible)
- **Impact of the issue**, including how an attacker might exploit it

### What to Expect

1. **Acknowledgment**: We'll confirm receipt of your vulnerability report within 48 hours
2. **Assessment**: We'll investigate and assess the severity within 5 business days
3. **Timeline**: We'll provide an expected timeline for a fix
4. **Resolution**: We'll notify you when the issue is fixed
5. **Disclosure**: We'll coordinate disclosure timing with you

## Security Update Process

1. Security patches are released as soon as possible after verification
2. Critical vulnerabilities receive immediate attention
3. Security releases are clearly marked in release notes
4. CVE identifiers are assigned for significant vulnerabilities

## Known Security Considerations

### Current Security Features

- **Zip Slip Protection**: Path traversal validation prevents directory escape attacks (CWE-22)
- **API Input Validation**: Upload size limits (100MB), MIME type checking, URL validation
- **Container Isolation**: Read-only source mounts, controlled data mounts
- **SSRF Prevention**: Blocks localhost and private IP addresses in URL scanning
- **Dependency Pinning**: All dependencies are pinned to specific versions

### Security Best Practices for Users

#### API Server Deployment

- **Never expose the API server directly to the public internet** without authentication
- Set `A11Y_API_TOKEN` environment variable to require API key authentication
- Use HTTPS reverse proxy (nginx, Caddy) in production
- Implement rate limiting at the reverse proxy level
- Run behind a firewall with restricted access

Example nginx configuration:
```nginx
server {
    listen 443 ssl;
    server_name scanner.example.com;

    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api:10m rate=10r/m;
    limit_req zone=api burst=5;

    location / {
        proxy_pass http://127.0.0.1:8008;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

#### Data Handling

- **Scrub sensitive URLs** from `data/results/*.json` before sharing artifacts
- **Review screenshots** in `data/results/*.png` for sensitive content
- **Rotate API tokens** regularly if using token authentication
- **Clean up old scan data** to prevent data accumulation

#### Container Security

- **Keep base images updated**: Regularly rebuild with latest Playwright image
- **Scan for vulnerabilities**: Use tools like `docker scan` or Trivy
- **Resource limits**: Set appropriate memory/CPU limits in production
- **Rootless mode**: Use rootless Podman or Docker where possible

Example resource limits:
```yaml
services:
  scanner:
    image: a11y-scanner:latest
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 2G
        reservations:
          cpus: '1.0'
          memory: 1G
```

#### Dependency Updates

- **Monitor security advisories** for Python packages
- **Review automated dependency updates** (e.g., Dependabot)
- **Test thoroughly** before updating dependencies in production

### Known Limitations

1. **Screenshot Data**: Screenshots may capture sensitive page content
2. **URL Logging**: All scanned URLs are logged and saved in JSON files
3. **No Built-in Auth**: API server has optional token auth only, not OAuth/SAML
4. **Rate Limiting**: No built-in rate limiting (must be added at proxy level)

## Security-Related Configuration

### Environment Variables

```bash
# Require API authentication
A11Y_API_TOKEN=your-secret-token-here

# Disable screenshots if they might contain sensitive data
A11Y_NO_SCREENSHOTS=1

# Container guard (automatically set, don't override)
A11Y_SCANNER_IN_CONTAINER=1
```

### Secure Token Generation

Generate strong API tokens:
```bash
# Linux/macOS
openssl rand -base64 32

# Python
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

## Vulnerability Disclosure Policy

We practice **coordinated disclosure**:

1. Security researchers have 90 days to report findings before public disclosure
2. We aim to patch critical vulnerabilities within 7 days
3. We'll work with you on disclosure timing
4. Public disclosure occurs after a patch is available

## Security Hall of Fame

We recognize security researchers who responsibly disclose vulnerabilities:

<!-- Add contributors here as they report issues -->
- *No vulnerabilities reported yet*

## Additional Resources

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [CWE Top 25](https://cwe.mitre.org/top25/)
- [Docker Security Best Practices](https://docs.docker.com/engine/security/)

## Contact

For security concerns: security@[yourdomain].com

For general questions: See [GitHub Discussions](https://github.com/yourusername/a11y-scanner/discussions)

---

**Note**: This security policy is subject to change. Last updated: 2025-01-XX
