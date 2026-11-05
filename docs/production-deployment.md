# Deploying sabay.org on a VPS

The examples use Linux/systemd, Python 3.14, user/group `sabay`, home
`/home/sabay`, and these paths:

| Purpose | Path |
| --- | --- |
| Git checkout | `/home/sabay/app` |
| pyenv installation | `/home/sabay/.pyenv` |
| SQLite database | `/home/sabay/data/db.sqlite3` |
| Collected static files | `/home/sabay/static` |
| Application environment | `/etc/sabay/app.env` |

Deployment runs automatically on pushes to `main`, including merged pull requests.
You can also run it manually: Actions → Deploy production → Run workflow → main.
The script installs locked dependencies, checks production settings, runs migrations,
collects static files, restarts Gunicorn and Daphne, and checks the HTTP app through
local Nginx. It contains no backup logic or automatic rollback. Merging these files
does not change the VPS.

## Questions and deployment behavior

- Confirm Python 3.14 is installed and selected with `pyenv global` for `sabay`, the existing database location, and whether these
  service names and ports conflict with anything already running.
- The supplied Nginx configuration preserves your basic authentication. Remove both
  `auth_basic` directives when you want the site public. It includes `sabay.org` only;
  add `www.sabay.org` only after configuring DNS and certificate coverage for it.
- In-place deployment can briefly interrupt requests and disconnect WebSockets.
  Dependencies, code, and static files may change while old workers are running.
  Use maintenance mode for incompatible migrations.
- Hosted GitHub runners must reach SSH. If SSH is private, use an appropriate private
  network connection or isolated deployment runner rather than opening it blindly.
- Existing CI runs on pull requests. Require its checks before merging to main.
  Deployment does not independently run tests or verify CI results.

## Why restricted SSH?

The Actions SSH key can invoke only the deployment script; it cannot open a shell
or forward ports. This works even while Django is down. A public deployment API
would require separate authentication, replay protection, job serialization, and
status tracking. Repository code, migrations, and package installation still execute
as `sabay`, so protect main and workflow changes. Both app services also run as
`sabay`, as requested; they share that account's file and deployment privileges.

## Production setup

1. **Prepare the account and checkout.** Use the existing `sabay` account, or create
   it with home `/home/sabay` if absent. Do not give it general passwordless sudo.
   As `sabay`, clone the repository into `/home/sabay/app`:

   ```bash
   git clone git@github.com:sabay-org/sabay.git /home/sabay/app
   export PYENV_ROOT=/home/sabay/.pyenv
   export PATH="$PYENV_ROOT/shims:$PYENV_ROOT/bin:$PATH"
   export PYENV_VERSION="$(pyenv global)"
   python --version
   python -m pip install pipenv
   cd /home/sabay/app
   python -m pipenv verify
   python -m pipenv sync --system
   pyenv rehash
   mkdir -p /home/sabay/data /home/sabay/static
   ```

   Dependencies are installed directly into the selected pyenv Python, without a
   virtual environment or sudo. Pipenv is used to verify/install `Pipfile.lock` with
   `--system`; it does not create a virtual environment. Deployment and both systemd
   units explicitly select `pyenv global`, so the repository's `.python-version`
   does not override production's interpreter. Keep the global version compatible
   with the project's Python 3.14 requirement. After changing it, install pipenv and
   locked dependencies into the new interpreter and restart both services.

   If private repository access is needed, give the server a separate read-only GitHub
   repository deploy key and verify GitHub's SSH host key. This is different from
   the Actions → VPS key below. If a checkout already exists, use it instead of cloning
   over it and resolve any tracked local edits without discarding production changes.

2. **Configure the production environment.** As an administrator:

   ```bash
   sudo install -d -o root -g sabay -m 0750 /etc/sabay
   sudo install -o root -g sabay -m 0640 deploy/app.env /etc/sabay/app.env
   sudoedit /etc/sabay/app.env
   ```

   Run the install command from the checkout only for initial setup. If app.env
   already exists, preserve its secret and database path and merge the deployment
   variables from `deploy/app.env` into it rather than overwriting it.

   `deploy/app.env` is the canonical configuration, with an empty secret that must
   be filled in on the server. The installed `/etc/sabay/app.env` is the single
   configuration file read by both systemd and the deployment script. It contains
   the app directory, pyenv root, health URL, space-separated `DEPLOY_SERVICES`, and
   Django settings. Use simple quoted assignments without `export` or Bash arrays.
   Keep the populated file outside Git; the development secret is public.

   To migrate an existing setup, copy the paths and service names from the old
   `/etc/sabay/deploy.conf` into app.env, using `DEPLOY_SERVICES` instead of the
   `SERVICES` array. Reinstall deploy.sh as described below. The old deploy.conf is
   no longer read and can be removed once migration is verified.

   If the app already has a database, stop all existing app services before moving
   that database into the configured location, and ensure `sabay` can write both the
   database and its directory. Do not unintentionally replace existing data with a
   newly initialized database. The provided settings use SQLite.

3. **Install and start the Python services.** From the checkout, as an administrator:

   ```bash
   sudo install -o root -g root -m 0644 deploy/sabay-gunicorn.service /etc/systemd/system/sabay-gunicorn.service
   sudo install -o root -g root -m 0644 deploy/sabay-daphne.service /etc/systemd/system/sabay-daphne.service
   sudo systemctl daemon-reload
   ```

   As `sabay`, initialize/check the application:

   ```bash
   cd /home/sabay/app
   export PYENV_ROOT=/home/sabay/.pyenv
   export PATH="$PYENV_ROOT/shims:$PYENV_ROOT/bin:$PATH"
   export PYENV_VERSION="$(pyenv global)"
   set -a
   source /etc/sabay/app.env
   set +a
   python manage.py check --deploy --fail-level WARNING
   python manage.py migrate --noinput
   python manage.py collectstatic --noinput
   ```

   Then as an administrator:

   ```bash
   sudo systemctl enable --now sabay-gunicorn.service sabay-daphne.service
   ```

   Gunicorn serves HTTP on `127.0.0.1:8000`; Daphne handles `/ws/` on
   `127.0.0.1:8001`. The current in-memory channel layer works within the single
   Daphne process. Configure shared Redis before scaling WebSockets across processes.
   Do not restart Redis for ordinary code deployments.

4. **Install the Nginx site.** The complete configuration is in
   [`deploy/nginx.conf`](../deploy/nginx.conf). It replaces the placeholder site:
   HTTPS Django proxy, static assets, WebSockets, preserved basic auth and Certbot
   certificate paths, IPv4/IPv6 listeners, and HTTP → HTTPS redirect.

   On Debian/Ubuntu, from the checkout:

   ```bash
   sudo install -o root -g root -m 0644 deploy/nginx.conf /etc/nginx/sites-available/sabay
   sudo ln -s /etc/nginx/sites-available/sabay /etc/nginx/sites-enabled/sabay
   ```

   Create the symlink only if it does not already exist. Disable the enabled file
   containing your old placeholder server blocks so the same domain is not defined
   twice. Preserve any unrelated hosted sites. The Certbot files and `.htpasswd`
   must already exist. Verify the Nginx worker user (commonly `www-data`) can read
   `.htpasswd` and static files. With Ubuntu's `acl` package installed, grant only
   the required home-directory traversal and static-file access:

   ```bash
   sudo setfacl -m u:www-data:--x /home/sabay
   sudo setfacl -R -m u:www-data:r-X /home/sabay/static
   sudo setfacl -m d:u:www-data:r-X /home/sabay/static
   sudo nginx -t
   sudo systemctl reload nginx
   ```

   Substitute the actual Nginx worker user if different. Default ACLs ensure newly
   collected assets remain readable without exposing the checkout or environment
   file. If deployment introduces nested asset directories, verify their inherited
   ACLs too. App ports are bound to loopback; do not expose them through another proxy
   or public listener. Nginx overwrites `X-Forwarded-Proto`, which Django trusts for
   HTTPS detection. TLS must work before enabling production HTTPS redirects/HSTS.
   Subdomain HSTS and preload are deferred; only those two Django warnings are silenced.

   Verify these checks on the server:

   ```bash
   curl --fail http://127.0.0.1:8080/
   curl --fail --user YOUR_BASIC_AUTH_USERNAME https://sabay.org/
   curl --fail --user YOUR_BASIC_AUTH_USERNAME https://sabay.org/static/css/simple.min.css
   ```

   `curl --user` prompts for the password. Port 8080 is bound only to loopback and
   bypasses basic auth solely for the deploy smoke check. Its root proxies the Django
   homepage with fixed trusted headers. It does not test public TLS, authentication,
   or WebSockets; verify those separately in a browser, including chat. Static updates
   need no Nginx reload; configuration changes require `nginx -t` and a reload.

5. **Install the restricted deploy command.** From the checkout:

   ```bash
   sudo install -o root -g root -m 0755 deploy/deploy.sh /usr/local/sbin/sabay-deploy
   ```

   Keep the installed script, `/etc/sabay/app.env`, and their
   parent directories root-owned and unwritable by `sabay`. Future script changes
   require administrator installation. With
   `sudo visudo -f /etc/sudoers.d/sabay-deploy`, add exactly:

   ```sudoers
   sabay ALL=(root) NOPASSWD: /usr/bin/systemctl restart sabay-gunicorn.service, /usr/bin/systemctl restart sabay-daphne.service
   ```

   Confirm `/usr/bin/systemctl` is the correct path. Do not allow arbitrary systemctl
   commands or shells. Keep units root-owned and run no app code as root.

6. **Create the Actions → VPS key.** On a trusted workstation:

   ```bash
   ssh-keygen -t ed25519 -f ./sabay-actions -C github-actions-sabay
   ```

   Use an empty passphrase for this automation-only key. Install the public key as
   one line in `/home/sabay/.ssh/authorized_keys`:

   ```text
   restrict,command="/usr/local/sbin/sabay-deploy" ssh-ed25519 AAAA... github-actions-sabay
   ```

   Set owner `sabay`, `.ssh` mode `0700`, and authorized_keys mode `0600`.
   Keep administrator credentials separate. Verify the VPS host key fingerprint
   through the Vultr console or another trusted channel, then prepare a matching
   known_hosts entry. Custom ports use `[hostname]:port`. Do not trust unverified
   `ssh-keyscan` output inside the workflow.

7. **Configure GitHub's `production` environment.** Restrict deployment branches to
   `main`. Protect main with required `CI / Ruff` and `CI / Django tests` checks.
   Configure these environment variables/secrets:

   | Kind | Name | Value |
   | --- | --- | --- |
   | Variable | `DEPLOY_HOST` | VPS hostname/address without a URL scheme |
   | Variable | `DEPLOY_USER` | `sabay` |
   | Variable | `DEPLOY_PORT` | SSH port; defaults to `22` |
   | Secret | `DEPLOY_SSH_KEY` | Entire private key from step 6 |
   | Secret | `DEPLOY_KNOWN_HOSTS` | Verified VPS known_hosts entry |

8. **Test and enable deployment.** From the trusted workstation, using an actual full
   main-branch commit SHA:

   ```bash
   ssh -i ./sabay-actions sabay@YOUR_VPS 'deploy FULL_40_CHARACTER_MAIN_SHA'
   ```

   Verify arbitrary commands and plain SSH sessions fail with this key. Verify the
   site and chat after deployment. Merge the workflow and run it manually on main.
   Workflow concurrency and server-side `flock` prevent overlapping deploys. The script
   verifies that the exact SHA belongs to main, rather than blindly pulling the
   latest code. Older main SHAs are allowed for deliberate recovery; GitHub does not
   guarantee queued deployment ordering.

## Failures

Actions reports failures in dependency installation, Django checks, migrations,
service restarts, or the local HTTP smoke check. Read the Actions log and
`journalctl -u sabay-gunicorn -u sabay-daphne`. The log records old and requested SHAs.
A lost SSH connection or the 30-minute workflow timeout may leave work partially
applied; inspect the host before retrying. The server lock remains held while the
original deployment process holds its file descriptor.

There is no automatic rollback. Reverting code does not undo schema/data migrations.
For a compatible schema, rerun the deploy command with a previous main SHA. A failed
in-place deployment can leave code, dependencies, and the database at different
versions; inspect these and correct the failed step before restarting services.
The local smoke check validates an HTTP response, not the running release SHA or
all application dependencies.

References: [Nginx WebSocket proxying](https://nginx.org/en/docs/http/websocket.html),
[Django with Daphne](https://docs.djangoproject.com/en/6.0/howto/deployment/asgi/daphne/),
[GitHub deployment environments](https://docs.github.com/en/actions/concepts/workflows-and-actions/deployment-environments).

Python tooling: [Pipenv CLI](https://pipenv.pypa.io/en/stable/cli.html),
[pyenv version selection](https://github.com/pyenv/pyenv/blob/master/COMMANDS.md).
