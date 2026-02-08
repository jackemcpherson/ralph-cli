# Publishing to PyPI

This guide documents the one-time setup required to enable automated publishing via [Trusted Publishers](https://docs.pypi.org/trusted-publishers/) (OpenID Connect). Once configured, pushing a git tag triggers the full release pipeline without any stored API tokens.

## Quick-Start Checklist

- [ ] Create the `ralph-cli` project on [PyPI](https://pypi.org) (if it doesn't exist yet)
- [ ] Create the `ralph-cli` project on [TestPyPI](https://test.pypi.org) (if it doesn't exist yet)
- [ ] Add a Trusted Publisher for **TestPyPI** (see [TestPyPI Configuration](#testpypi-configuration))
- [ ] Add a Trusted Publisher for **PyPI** (see [PyPI Configuration](#pypi-configuration))
- [ ] Create the `testpypi` GitHub Actions environment in repository settings
- [ ] Create the `pypi` GitHub Actions environment in repository settings
- [ ] Push a tag (`git tag vX.Y.Z && git push origin vX.Y.Z`) and verify the pipeline runs end-to-end

## How It Works

The publish workflow (`.github/workflows/publish.yml`) uses the `pypa/gh-action-pypi-publish` action with OIDC authentication. GitHub Actions requests a short-lived token from PyPI/TestPyPI on each run — no long-lived API tokens are stored as repository secrets.

The pipeline runs in order:

1. **ci-check** — waits for the CI workflow to pass on the tagged commit
2. **build** — builds the sdist and wheel with `uv build`
3. **testpypi** — uploads to TestPyPI for validation
4. **pypi** — uploads to production PyPI
5. **release** — creates a GitHub Release with changelog notes and attached artifacts

## TestPyPI Configuration

Configure a Trusted Publisher on TestPyPI so the `testpypi` job can upload packages.

1. Go to <https://test.pypi.org/manage/account/publishing/>
2. Under **Add a new pending publisher** (or under the project's Publishing settings if the project already exists), enter:

| Field | Value |
|-------|-------|
| PyPI project name | `ralph-cli` |
| Owner | `jackemcpherson` |
| Repository name | `ralph-cli` |
| Workflow name | `publish.yml` |
| Environment name | `testpypi` |

3. Click **Add**

## PyPI Configuration

Configure a Trusted Publisher on production PyPI so the `pypi` job can upload packages.

1. Go to <https://pypi.org/manage/account/publishing/>
2. Under **Add a new pending publisher** (or under the project's Publishing settings if the project already exists), enter:

| Field | Value |
|-------|-------|
| PyPI project name | `ralph-cli` |
| Owner | `jackemcpherson` |
| Repository name | `ralph-cli` |
| Workflow name | `publish.yml` |
| Environment name | `pypi` |

3. Click **Add**

## GitHub Actions Environments

The publish workflow requires two GitHub Actions environments for deployment protection. Create them in the repository settings:

1. Go to **Settings > Environments** in the GitHub repository
2. Create an environment named **`testpypi`**
   - Optionally add deployment protection rules (e.g., required reviewers)
3. Create an environment named **`pypi`**
   - Recommended: add a required reviewer for production deployments

## Triggering a Release

Once the Trusted Publishers and environments are configured:

```bash
# Ensure version is updated in pyproject.toml, src/ralph/__init__.py, and CHANGELOG.md
git tag v2.1.0
git push origin v2.1.0
```

The publish workflow triggers automatically on tag pushes matching `v*`.

## Troubleshooting

### "Token request failed" or OIDC errors

- Verify the Trusted Publisher configuration matches exactly (owner, repo, workflow name, environment name)
- Ensure the GitHub Actions environment exists and matches the name in the workflow YAML
- Check that the workflow has `id-token: write` permission

### TestPyPI upload succeeds but PyPI fails

- Confirm the PyPI Trusted Publisher is configured separately from TestPyPI — they are independent registries
- Check that the `pypi` environment exists in GitHub repository settings

### CI check times out

- The `ci-check` job waits up to 15 minutes for CI to complete on the tagged commit
- Ensure the CI workflow (`ci.yml`) triggers on tag pushes (`tags: ['v*']`)

## References

- [PyPI Trusted Publishers documentation](https://docs.pypi.org/trusted-publishers/)
- [pypa/gh-action-pypi-publish](https://github.com/pypa/gh-action-pypi-publish)
- [GitHub Actions: Using OpenID Connect](https://docs.github.com/en/actions/security-for-github-actions/security-hardening-your-deployments/about-security-hardening-with-openid-connect)
