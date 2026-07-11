# Contributing

Thanks for helping improve MARK XXXIX.

## Local setup

1. Install Python 3.11 or 3.12.
2. Install dependencies:

```bash
python -m pip install -r requirements.txt
python -m playwright install chromium
```

3. Create local credentials:

```bash
python setup_keys.py
```

Never commit real credentials. Use `.env.example` and `config/api_keys.example.json`
as templates.

## Development guidelines

- Keep changes focused and small enough to review.
- Prefer local, explicit safety checks before adding automation that controls apps,
  browsers, files, network settings, power settings, or trading tools.
- Update the README or relevant docs when changing setup, config, or user-facing
  behavior.
- Do not commit generated caches, browser profiles, logs, local memory, or vault
  files that contain personal data.

## Pull requests

Before opening a pull request:

- Run the relevant app entry point or smoke test locally.
- Check that no real API keys, tokens, passwords, cookies, or browser profile data
  are included.
- Describe what changed, why it changed, and how it was tested.
