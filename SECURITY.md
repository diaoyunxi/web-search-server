# Security Policy

## Reporting a Vulnerability

Please report security issues via GitHub Issues (private) or email.

## Security Considerations

- Set API key to restrict access (`DEEPSEEK_API_KEY` env var)
- Restrict CORS origins in production (currently `*`)
- Add request body size limits
- Bind to localhost if not exposed externally
- Use HTTPS via reverse proxy in production
