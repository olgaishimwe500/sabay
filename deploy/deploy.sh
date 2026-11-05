#!/usr/bin/env bash
# Install as a root-owned file; execute as the unprivileged deploy user.
set -euo pipefail
export PATH=/usr/local/bin:/usr/bin:/bin
umask 027

# Shared with systemd; this root-owned file is trusted configuration.
set -a
source /etc/sabay/app.env
set +a
: "${APP_DIR:?}" "${PYENV_ROOT:?}" "${HEALTH_URL:?}" "${DEPLOY_SERVICES:?}"
read -r -a services <<< "$DEPLOY_SERVICES"
[[ "${SSH_ORIGINAL_COMMAND:-}" =~ ^deploy\ ([0-9a-f]{40})$ ]] || {
  echo 'Only deploy <40-character commit SHA> is allowed.' >&2
  exit 1
}
revision=${BASH_REMATCH[1]}
exec 9>"$APP_DIR/.deploy.lock"
flock -n 9 || { echo 'A deployment is already running.' >&2; exit 1; }
trap 'echo "Deploy failed at line $LINENO; inspect services and restore manually if needed." >&2' ERR
cd "$APP_DIR"
[[ -z "$(git status --porcelain --untracked-files=no)" ]] || {
  echo 'Tracked production files have local edits; refusing deployment.' >&2
  exit 1
}
git fetch --prune origin '+refs/heads/main:refs/remotes/origin/main'
git merge-base --is-ancestor "$revision" origin/main
previous=$(git rev-parse HEAD)
printf 'Deploying %s (previous %s)\n' "$revision" "$previous"

# Use the account's global pyenv selection, independent of the checkout's .python-version.
export PYENV_ROOT
export PATH="$PYENV_ROOT/shims:$PYENV_ROOT/bin:$PATH"
export PYENV_VERSION="$(pyenv global)"
unset VIRTUAL_ENV
export PIPENV_IGNORE_VIRTUALENVS=1

git checkout --detach "$revision"
python -m pipenv verify
python -m pipenv sync --system
pyenv rehash
python manage.py check --deploy --fail-level WARNING
python manage.py migrate --noinput
python manage.py collectstatic --noinput
for service in "${services[@]}"; do
  sudo -n /usr/bin/systemctl restart "$service"
  /usr/bin/systemctl is-active --quiet "$service"
done
curl --fail --silent --show-error --retry 12 --retry-delay 5 \
  --retry-connrefused --retry-all-errors --connect-timeout 5 --max-time 10 \
  "$HEALTH_URL" > /dev/null
printf 'Successfully deployed %s\n' "$revision"
