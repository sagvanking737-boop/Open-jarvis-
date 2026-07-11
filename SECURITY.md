# Security Policy

## Reporting a Vulnerability

Do not open a public issue for secrets, authentication bypasses, unsafe desktop
automation behavior, or other exploitable vulnerabilities.

Report security issues privately to the project maintainers. Include:

- A short description of the issue.
- Steps to reproduce it.
- The affected files or features.
- Any suggested mitigation, if known.

## Sensitive Data

This project can integrate with API providers, local apps, browser profiles, and
desktop automation. Treat the following as private local data:

- `.env`
- `config/api_keys.json`
- `.data/`
- `.logs/`
- `memory/long_term.json`
- Vault notes containing API keys, tokens, credentials, or personal data.

Rotate any key that was committed or shared accidentally.

## Automation Safety

Features that control the browser, desktop, phone, files, power settings, or
trading workflows should default to safe behavior and require explicit user
configuration before performing high-impact actions.
