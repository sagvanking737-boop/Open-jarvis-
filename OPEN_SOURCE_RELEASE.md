# Open Source Release Checklist

Use this checklist before publishing the repository.

## Required

- [ ] Rename or rebrand the project if needed to avoid third-party trademark or
      copyright confusion.
- [ ] Confirm the code license in `LICENSE` matches the intended release model.
- [ ] Remove or ignore local credentials and personal data.
- [ ] Confirm `.env`, `config/api_keys.json`, `.data/`, `.logs/`, local memory,
      browser profiles, and private vault notes are not tracked.
- [ ] Replace private config with `.env.example` and
      `config/api_keys.example.json`.
- [ ] Review bundled binaries under `bin/` and confirm their licenses permit
      redistribution, or remove them and document installation instead.
- [ ] Curate any `vault/` content before publishing. Keep personal notes,
      contacts, strategy docs, API-key notes, and daily logs private.
- [ ] Run a smoke test from a clean checkout.

## Recommended

- [ ] Add screenshots or a short demo video after removing personal data.
- [ ] Add issue templates for bugs and feature requests.
- [ ] Add a minimal CI workflow for linting or import checks.
- [ ] Document which integrations are optional and which external accounts are
      required.

## Suggested publish commands

```bash
git init
git add .
git status
git commit -m "Initial open-source release"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPOSITORY.git
git push -u origin main
```
