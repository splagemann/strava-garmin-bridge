# Docker Image Publishing Workflow

This repository includes a GitHub Actions workflow that automatically builds and publishes Docker images for both the backend and frontend to GitHub Container Registry (GHCR).

## Overview

The workflow builds:
- **Backend**: Python FastAPI application (`ghcr.io/<owner>/strava-garmin-bridge/backend`)
- **Frontend**: React + Vite application (`ghcr.io/<owner>/strava-garmin-bridge/frontend`)

## Semantic Versioning

This project follows [Semantic Versioning 2.0.0](https://semver.org/):
- **MAJOR** version (v1.0.0 → v2.0.0): Incompatible API changes
- **MINOR** version (v1.0.0 → v1.1.0): New functionality (backwards compatible)
- **PATCH** version (v1.0.0 → v1.0.1): Bug fixes (backwards compatible)

## Conventional Commits

Use [Conventional Commits](https://www.conventionalcommits.org/) for automatic changelog generation:
- `feat:` - New feature (MINOR version bump)
- `fix:` - Bug fix (PATCH version bump)
- `feat!:` or `BREAKING CHANGE:` - Breaking change (MAJOR version bump)
- `docs:` - Documentation changes
- `chore:` - Maintenance tasks
- `refactor:` - Code refactoring
- `perf:` - Performance improvements
- `test:` - Testing updates

### Examples

```bash
# Feature (will appear in changelog under "Features")
git commit -m "feat: add OAuth integration for Strava"

# Bug fix (will appear under "Bug Fixes")
git commit -m "fix: resolve sync timing issue"

# Breaking change (requires MAJOR version bump)
git commit -m "feat!: redesign API authentication flow

BREAKING CHANGE: Previous token-based auth is no longer supported"

# With scope
git commit -m "fix(frontend): correct activity display formatting"
```

## Triggers

The workflow runs on:
- **Push to main**: Builds and publishes images tagged as `latest` and `main-<sha>`
- **Tag push** (e.g., `v1.0.0`): Builds versioned images, generates changelog, and creates GitHub release
- **Pull requests**: Builds images but doesn't publish (for testing)
- **Manual dispatch**: Can be triggered manually from the Actions tab

## Image Tags

Images are automatically tagged with:
- `latest` - Latest build from the main branch
- `main` - Main branch builds
- `v1.2.3` - Semantic version tags
- `v1.2` - Major.minor version
- `v1` - Major version
- `main-<sha>` - Commit SHA for traceability
- `pr-<number>` - Pull request builds (not pushed)

## Setup Instructions

### 1. Enable GitHub Packages

No special setup is required! The workflow uses `GITHUB_TOKEN` which is automatically provided by GitHub Actions.

### 2. Configure Frontend API URL (Optional)

If you need to set a custom API URL for the frontend build:

1. Go to your repository **Settings** → **Secrets and variables** → **Actions**
2. Click **New repository secret**
3. Name: `VITE_API_URL`
4. Value: Your API URL (e.g., `https://api.yourdomain.com`)

If not set, it defaults to `http://localhost:8000`.

### 3. Enable Multi-Architecture Builds (Optional)

The workflow builds for both `linux/amd64` and `linux/arm64` by default. If you only need one architecture, remove the unwanted platform from the `platforms` line in `.github/workflows/docker-publish.yml`.

## Usage

### Automatic Builds

**On every push to main:**
```bash
git push origin main
```

This will:
1. Build both backend and frontend images
2. Push them to GHCR with `latest` and `main-<sha>` tags

**Create a release:**
```bash
# Tag with semantic version
git tag v1.0.0
git push origin v1.0.0
```

This will:
1. Generate a changelog from conventional commits
2. Create a GitHub release with the changelog
3. Build and push versioned Docker images:
   - `ghcr.io/<owner>/<repo>/backend:v1.0.0`
   - `ghcr.io/<owner>/<repo>/backend:v1.0`
   - `ghcr.io/<owner>/<repo>/backend:v1`
   - `ghcr.io/<owner>/<repo>/frontend:v1.0.0`
   - `ghcr.io/<owner>/<repo>/frontend:v1.0`
   - `ghcr.io/<owner>/<repo>/frontend:v1`

**Automated release process:**

The workflow automatically:
1. Detects the version tag
2. Generates a changelog from commits since the last tag
3. Creates a GitHub release with the changelog
4. Builds and publishes Docker images with proper semantic version tags

**Manual trigger:**
1. Go to **Actions** tab in your repository
2. Select **Build and Publish Docker Images**
3. Click **Run workflow**
4. Select branch and click **Run workflow**

## Pulling Images

### Public Repositories

Images are automatically public. Pull them directly:

```bash
# Backend
docker pull ghcr.io/<owner>/<repo>/backend:latest

# Frontend
docker pull ghcr.io/<owner>/<repo>/frontend:latest
```

### Private Repositories

For private repositories, authenticate first:

```bash
# Create a Personal Access Token with read:packages scope
# Go to: GitHub Settings → Developer settings → Personal access tokens → Tokens (classic)

# Login to GHCR
echo $GITHUB_TOKEN | docker login ghcr.io -u USERNAME --password-stdin

# Pull images
docker pull ghcr.io/<owner>/<repo>/backend:latest
docker pull ghcr.io/<owner>/<repo>/frontend:latest
```

## Using with Docker Compose

Create a `docker-compose.prod.yml` file:

```yaml
version: '3.8'

services:
  backend:
    image: ghcr.io/<owner>/<repo>/backend:latest
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=${REDIS_URL}
      # Add other environment variables
    env_file:
      - .env

  frontend:
    image: ghcr.io/<owner>/<repo>/frontend:latest
    ports:
      - "80:80"
    depends_on:
      - backend
```

Run it:
```bash
docker-compose -f docker-compose.prod.yml up -d
```

## Making Images Public

By default, images are private. To make them public:

1. Go to your repository page on GitHub
2. Click on **Packages** (right sidebar)
3. Click on your package (backend or frontend)
4. Click **Package settings**
5. Scroll down to **Danger Zone**
6. Click **Change visibility** → **Public**

## Monitoring Builds

1. Go to the **Actions** tab in your repository
2. Click on **Build and Publish Docker Images**
3. View running or completed workflow runs
4. Click on a run to see detailed logs

## Caching

The workflow uses GitHub Actions cache to speed up builds:
- Docker layer caching is enabled
- Subsequent builds will be much faster
- Cache is automatically managed by GitHub

## Changelog Generation

The workflow uses [git-cliff](https://git-cliff.org/) to automatically generate changelogs from conventional commits.

### Configuration

The changelog is configured in `cliff.toml`. Customize it to:
- Change commit grouping
- Modify the changelog format
- Filter specific commit types
- Add custom commit parsers

### Manual changelog generation

Generate a changelog locally:

```bash
# Install git-cliff
cargo install git-cliff

# Generate full changelog
git-cliff --output CHANGELOG.md

# Generate changelog for latest tag
git-cliff --latest --output RELEASE_NOTES.md

# Generate changelog between tags
git-cliff v1.0.0..v1.1.0
```

## Release Workflow

### Complete release process:

```bash
# 1. Ensure all changes are committed with conventional commits
git status

# 2. Review commits since last release
git log $(git describe --tags --abbrev=0)..HEAD --oneline

# 3. Determine version bump (major.minor.patch)
# - Breaking changes = MAJOR
# - New features = MINOR
# - Bug fixes = PATCH

# 4. Create and push tag
git tag v1.2.3
git push origin v1.2.3

# 5. GitHub Actions automatically:
#    - Generates changelog
#    - Creates GitHub release
#    - Builds Docker images
#    - Publishes to GHCR
```

## Troubleshooting

### Build fails with permission error
- Ensure the workflow has `packages: write` permission (already configured)
- Check that Actions are enabled in repository settings

### Changelog generation fails
- Ensure commits follow conventional commit format
- Check `cliff.toml` configuration is valid
- Verify git tags follow `v*` pattern (e.g., `v1.0.0`)

### GitHub release not created
- Ensure the workflow has `contents: write` permission
- Check that you're pushing a tag matching `v*`
- Verify `GITHUB_TOKEN` has sufficient permissions

### Frontend API URL not set correctly
- Set the `VITE_API_URL` secret in repository settings
- Or modify the default in `.github/workflows/docker-publish.yml`

### Images not appearing in packages
- Check that the workflow completed successfully
- Verify the workflow is running on push/tag events
- Ensure you're not on a pull request (PRs don't push images)

### Cannot pull private images
- Create a Personal Access Token with `read:packages` scope
- Login using: `docker login ghcr.io -u USERNAME`

## Advanced Configuration

### Change Image Names

Edit the `env` section in `.github/workflows/docker-publish.yml`:

```yaml
env:
  REGISTRY: ghcr.io
  BACKEND_IMAGE_NAME: ${{ github.repository }}/my-api
  FRONTEND_IMAGE_NAME: ${{ github.repository }}/my-web
```

### Add Build Arguments

Add more build arguments in the frontend build step:

```yaml
build-args: |
  VITE_API_URL=${{ secrets.VITE_API_URL }}
  VITE_OTHER_VAR=${{ secrets.OTHER_VAR }}
```

### Only Build on Tags

To only publish on version tags, modify the `on` section:

```yaml
on:
  push:
    tags:
      - 'v*'
  workflow_dispatch:
```

## Resources

- [GitHub Packages Documentation](https://docs.github.com/en/packages)
- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Docker Build Action](https://github.com/docker/build-push-action)
