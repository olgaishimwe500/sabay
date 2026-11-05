## Local development setup

* highly recommend running linux (Ubuntu 24.04 (via VM if you run another host OS))
* install / setup [pyenv](https://github.com/pyenv/pyenv)
* from top-level repo directory...
* install version specified in `.python-version` file
  - `pyenv install`
* ensure you're picking up correct version of python
  - `cat .python-version && python --version`
* create virtual environment for localized package installation
  - `python -m venv .venv`
* active virtual env
  - linux / macOS: `source .venv/bin/activate`
  - windows: mmm, you should look it up; depends on terminal environment used
* install [pipenv](https://pipenv.pypa.io/en/latest/installation.html)
  - `pip install pipenv`
* install project packages
  - `pipenv install`

## Quality checks

Run the same checks used by continuous integration before opening a pull request:

```bash
ruff check .
pipenv run python manage.py check
pipenv run python manage.py makemigrations --check --dry-run
pipenv run python manage.py test
```

The `CI` GitHub Actions workflow runs linting and tests whenever a pull request is
opened, updated, reopened, or marked ready for review. Configure the repository's
branch rules to require the `CI / Ruff` and `CI / Django tests` status checks before
merging.

## Git hooks

> [!CAUTION]
> Always review git hooks.

Enable git hooks for auto-formatting on commit using `Ruff`.

```bash
git config --local core.hooksPath .githooks
```

## Production deployment

See [the VPS deployment guide](docs/production-deployment.md) for the manual GitHub
Actions workflow, restricted SSH setup, server script, and production rollout steps.
