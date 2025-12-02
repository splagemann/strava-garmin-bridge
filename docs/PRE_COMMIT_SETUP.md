# Pre-commit Hooks Setup

This project uses pre-commit hooks to enforce code quality and conventional commit messages.

## What's Included

### Commit Message Validation
- **Conventional Commits**: Ensures all commit messages follow the [Conventional Commits](https://www.conventionalcommits.org/) format
- Allowed types: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, `revert`

### Code Quality (Python)
- **black**: Automatic code formatting
- **isort**: Import statement sorting
- **bandit**: Security vulnerability scanning
- **detect-secrets**: Prevents committing secrets

### General Checks
- Trailing whitespace removal
- End-of-file fixer
- YAML/JSON/TOML validation
- Large file detection (max 500KB)
- Merge conflict detection
- Private key detection

## Installation

### Quick Setup

```bash
# Install development dependencies (includes pre-commit)
pip install -r backend/requirements-dev.txt

# Install pre-commit hooks
pre-commit install --hook-type pre-commit --hook-type commit-msg

# Test the setup
pre-commit run --all-files
```

### Detailed Steps

#### 1. Install pre-commit

```bash
# Option 1: Via pip
pip install pre-commit

# Option 2: Via Homebrew (macOS)
brew install pre-commit

# Option 3: Via apt (Ubuntu/Debian)
sudo apt install pre-commit
```

#### 2. Install git hooks

```bash
# Install both pre-commit and commit-msg hooks
pre-commit install --hook-type pre-commit --hook-type commit-msg
```

You should see:
```
pre-commit installed at .git/hooks/pre-commit
pre-commit installed at .git/hooks/commit-msg
```

#### 3. Verify installation

```bash
# Run all hooks manually
pre-commit run --all-files
```

## Usage

### Normal Workflow

Once installed, pre-commit hooks run automatically:

```bash
# Stage your changes
git add .

# Try to commit (hooks will run automatically)
git commit -m "feat: add new feature"
```

**If your commit message is invalid:**
```bash
$ git commit -m "Added new feature"
[INFO] Initializing environment for https://github.com/compilerla/conventional-pre-commit.
Conventional Commit......................................................Failed
- hook id: conventional-pre-commit
- duration: 0.12s
- exit code: 1

❌ Invalid commit message format!
```

**If your code needs formatting:**
```bash
$ git commit -m "feat: add new feature"
black....................................................................Failed
- hook id: black
- files were modified by this hook

Files reformatted:
- backend/app/main.py

# Re-add the formatted files and commit again
git add .
git commit -m "feat: add new feature"
```

### Valid Commit Message Examples

```bash
# Feature
git commit -m "feat: add OAuth integration for Strava"

# Bug fix
git commit -m "fix: resolve sync timing issue"

# Bug fix with scope
git commit -m "fix(frontend): correct activity display formatting"

# Breaking change
git commit -m "feat!: redesign API authentication

BREAKING CHANGE: Previous token-based auth is no longer supported"

# Documentation
git commit -m "docs: update setup instructions"

# Refactoring
git commit -m "refactor: simplify sync logic"

# Performance improvement
git commit -m "perf: optimize database queries"

# Tests
git commit -m "test: add unit tests for sync service"

# Build/CI
git commit -m "ci: update GitHub Actions workflow"

# Chores
git commit -m "chore: update dependencies"
```

### Invalid Commit Message Examples

```bash
# ❌ No type prefix
git commit -m "Added new feature"

# ❌ Wrong case
git commit -m "FEAT: add new feature"

# ❌ Missing colon
git commit -m "feat add new feature"

# ❌ Empty subject
git commit -m "feat: "

# ❌ Subject ends with period
git commit -m "feat: add new feature."

# ❌ Invalid type
git commit -m "feature: add new feature"
```

### Skipping Hooks (Not Recommended)

If you need to bypass hooks (emergency only):

```bash
# Skip all hooks
git commit -m "emergency fix" --no-verify

# Or
SKIP=pre-commit git commit -m "emergency fix"
```

⚠️ **Warning**: Only use this in emergencies. The CI pipeline will still enforce these rules.

### Running Hooks Manually

```bash
# Run all hooks on all files
pre-commit run --all-files

# Run specific hook
pre-commit run black --all-files
pre-commit run conventional-pre-commit --hook-stage commit-msg --commit-msg-filename .git/COMMIT_EDITMSG

# Run hooks on specific files
pre-commit run --files backend/app/main.py backend/app/config.py

# Run hooks on staged files only
pre-commit run
```

### Updating Hooks

```bash
# Update all hooks to latest versions
pre-commit autoupdate

# Clean and reinstall hooks
pre-commit clean
pre-commit install --hook-type pre-commit --hook-type commit-msg
```

## Configuration Files

### `.pre-commit-config.yaml`
Main configuration file defining all hooks and their settings.

### `.commitlintrc.json`
Commit message validation rules (compatible with commitlint).

### `backend/pyproject.toml`
Configuration for black, isort, and bandit.

### `backend/.secrets.baseline`
Baseline for detect-secrets plugin to avoid false positives.

## Troubleshooting

### Hook installation failed
```bash
# Clean existing hooks and reinstall
rm -rf .git/hooks/pre-commit .git/hooks/commit-msg
pre-commit install --hook-type pre-commit --hook-type commit-msg
```

### Hooks not running
```bash
# Check if hooks are installed
ls -la .git/hooks/

# Should show:
# - pre-commit
# - commit-msg

# Reinstall if missing
pre-commit install --hook-type pre-commit --hook-type commit-msg
```

### Python version mismatch
```bash
# Ensure you're using Python 3.11+
python --version

# Update hook to use specific Python version
pre-commit run --all-files --hook-stage commit
```

### "detect-secrets" baseline errors
```bash
# Update secrets baseline
detect-secrets scan > .secrets.baseline

# Or install detect-secrets
pip install detect-secrets
```

### Black formatting conflicts
```bash
# Run black manually
black backend/app/

# Add formatted files
git add .
git commit -m "style: apply black formatting"
```

## Docker Integration

To use pre-commit hooks in Docker:

```bash
# Add to Dockerfile (development image)
RUN pip install pre-commit
COPY .pre-commit-config.yaml .
RUN git config --global --add safe.directory /app && \
    pre-commit install --hook-type pre-commit --hook-type commit-msg

# Or run in development container
docker-compose exec web pip install pre-commit
docker-compose exec web pre-commit install --hook-type pre-commit --hook-type commit-msg
```

## CI/CD Integration

The GitHub Actions workflow already includes:
- Conventional commit validation for changelog generation
- Code formatting checks
- Security scanning

Pre-commit hooks provide **local validation** before pushing, reducing CI failures.

## Disabling Specific Hooks

Edit `.pre-commit-config.yaml` and comment out unwanted hooks:

```yaml
repos:
  - repo: https://github.com/psf/black
    rev: 24.10.0
    hooks:
      - id: black
        # Temporarily disable black
        # language_version: python3.11
```

Or skip specific hooks:

```bash
# Skip black for one commit
SKIP=black git commit -m "feat: add feature"

# Skip multiple hooks
SKIP=black,isort git commit -m "feat: add feature"
```

## IDE Integration

### VS Code

Install extensions:
- **Python** (Microsoft)
- **Black Formatter** (Microsoft)
- **isort** (Microsoft)

Add to `.vscode/settings.json`:
```json
{
  "python.formatting.provider": "black",
  "python.linting.enabled": true,
  "editor.formatOnSave": true,
  "[python]": {
    "editor.defaultFormatter": "ms-python.black-formatter",
    "editor.codeActionsOnSave": {
      "source.organizeImports": true
    }
  }
}
```

### PyCharm

1. Go to **Settings** → **Tools** → **File Watchers**
2. Add watchers for:
   - Black (on Python files)
   - isort (on Python files)

## Resources

- [Conventional Commits](https://www.conventionalcommits.org/)
- [pre-commit Documentation](https://pre-commit.com/)
- [black Documentation](https://black.readthedocs.io/)
- [isort Documentation](https://pycqa.github.io/isort/)
- [bandit Documentation](https://bandit.readthedocs.io/)
