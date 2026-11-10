# Repository context for coding agents

## Project and sources of truth

Sabay is an MIT-licensed Portland State University capstone project for connecting
people seeking non-medical help at home with local caregivers/helpers. Favor clear,
accessible, mobile-friendly interfaces suitable for older and less technical users.

- `README.md`: local setup, checks, and Git hook setup.
- `docs/production-deployment.md`: detailed VPS installation and recovery guide.
- `docs/project_document.tex`: product vision and proposed scope, dated August 2026.
  Its implementation-status section predates authentication, chat, and deployment
  work. Proposed booking, payments, verification, and other platform features are
  not evidence that those features exist or have been approved for implementation.
- Inspect current source and workflows when documentation disagrees with them.
  Repository files describe the intended server setup; they do not prove what is
  currently installed or running on the VPS.

## Application layout

- Python/Django application using Django templates, Simple.css, and SQLite.
  `.python-version` specifies the local/CI interpreter; `Pipfile` requires Python
  3.14. Use `Pipfile.lock` for locked dependencies.
- `sabay/`: project settings, URL routing, home/dashboard views, WSGI and ASGI entry
  points, and basic page/static-file tests.
- `members/`: custom login/logout views using Django's built-in authentication.
  Logout requires POST. This is not yet a complete account-management platform.
- `chat/`: Django Channels room chat, templates, routing, and WebSocket consumer.
  The current consumer broadcasts room messages without persisting them; do not
  assume private messaging, participant authorization, or message history exists.
- `templates/` and `static/`: shared UI and static assets; chat also has app-local
  templates/static assets.
- `sabay/settings.py` is development configuration, including a public development
  secret. `sabay/production_settings.py` imports it and applies production overrides.
- The channel layer currently runs in memory. Redis dependencies are installed but
  Redis is not the active channel backend. Shared Redis is needed before scaling
  WebSockets across processes.

## Development and verification

Follow the README's pyenv/virtualenv/Pipenv setup. Run checks in the configured
environment; do not assume a global Python or installed dependencies match it.

```bash
ruff check .
pipenv run python manage.py check
pipenv run python manage.py makemigrations --check --dry-run
pipenv run python manage.py test
```

CI runs these categories of checks for pull requests. Add migrations when changing
models. Ruff's configuration is in `ruff.toml` (Python 3.14, 88-column formatting).
The optional `.githooks` pre-commit hook formats and re-stages changed Python files;
review hooks before enabling them with `git config --local core.hooksPath .githooks`.

## Production deployment

- `.github/workflows/deploy.yml` deploys pushes to `main` and supports manual runs
  on `main`. It uses the GitHub `production` environment and restricted SSH to invoke
  `deploy <full 40-character SHA>` on the VPS.
- `deploy/deploy.sh` is installed as root-owned
  `/usr/local/sbin/sabay-deploy`, but executes as the unprivileged `sabay` user.
  Changes to the repo script require administrator reinstallation to take effect.
- The script locks deployments, refuses tracked local edits, fetches main, verifies
  the requested SHA belongs to main, and checks out that exact SHA detached. Older
  main SHAs are allowed for recovery.
- It verifies/syncs locked dependencies into the account's global pyenv interpreter,
  runs production checks, migrations, and collectstatic, restarts the configured
  services, and checks HTTP through local Nginx. Production intentionally selects
  `pyenv global`, independently of the checkout's `.python-version`.
- Default paths: checkout `/home/sabay/app`, database
  `/home/sabay/data/db.sqlite3`, collected static files `/home/sabay/static`, pyenv
  `/home/sabay/.pyenv`.
- Nginx proxies HTTP to Gunicorn at `127.0.0.1:8000` and WebSockets to Daphne at
  `127.0.0.1:8001`. A loopback-only Nginx listener at port 8080 provides the deploy
  smoke check. Public basic authentication is retained in the supplied Nginx config.
- Units and Nginx configuration are installed copies, not live repo references.
  Infrastructure changes need installation/reload as documented. App code runs as
  `sabay`; sudo permits only the specified service restarts.
- Deployment is in place, can interrupt requests/WebSockets, and has no automatic
  rollback or backup step. Reverting code does not reverse migrations. The smoke
  check does not verify the running release SHA, public TLS/auth, or WebSockets.
- Known documentation mismatch: the workflow reads `DEPLOY_HOST` from GitHub
  **secrets**, while the deployment guide lists it as a variable. Follow the actual
  workflow unless deliberately changing both.

## Environment configuration: current behavior and user intent

- `deploy/app.env` is an installation template. Initial setup copies it to
  `/etc/sabay/app.env`; normal deploys do not copy or load the repo version.
- Both the installed deployment script and the systemd units read
  `/etc/sabay/app.env`. It holds deployment paths/service names, Django settings
  selection, the production secret, and database/static paths. Preserve populated
  secrets and existing data paths when updating it; never commit server secrets.
  Assignments must work with both Bash sourcing and systemd's environment-file
  syntax (simple assignments, no `export` or Bash arrays).
- The user wants to change non-sensitive configuration in Git and have ordinary
  deployments apply it without repeated server infrastructure changes.
- Non-sensitive Django settings can already be edited directly in
  `sabay/production_settings.py` and take effect on deployment.
- We discussed a possible future split for actual environment variables: repo-managed
  defaults followed by `/etc/sabay/app.env` secrets/server overrides. **This split
  has not been implemented.** It would require a one-time update of the installed
  deployment script and units. Any implementation must load defaults from the
  requested checkout after checkout, give server overrides precedence, and keep
  management commands and restarted services consistent.

## Useful history anchors

- `195312c`: production deployment triggered by pushes to main.
- `343b53a` (#53): production settings, deploy script, units, Nginx, and deployment guide.
- `75b729a` (#33): Channels chat integration.
- `be52d5f` (#42): authentication and navigation.
- `89eb96b` (#34), `43c9923`: project planning document and follow-up edits.
- `9113ff9` (#28): Ruff formatting Git hook.
- `763d02a` (#25): lint/test CI; `1fd0335` (#24): Simple.css foundation.

Keep this file updated when architecture, deployment behavior, or established
project decisions change. Distinguish implemented behavior from proposals.
