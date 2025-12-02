# Contributing to Strava-Garmin Sync Bridge

Thank you for your interest in contributing! This document provides guidelines and instructions for contributing to the project.

## Getting Started

1. **Fork the repository** on GitHub
2. **Clone your fork** locally:
   ```bash
   git clone https://github.com/YOUR_USERNAME/strava-garmin-bridge.git
   cd strava-garmin-bridge
   ```
3. **Set up the development environment** (see below)
4. **Create a feature branch**:
   ```bash
   git checkout -b feat/your-feature-name
   ```

## Development Environment Setup

### Prerequisites

- Python 3.11+
- PostgreSQL
- Redis
- Docker & Docker Compose (optional but recommended)
- Node.js 20+ (for frontend development)

### Installation

#### Backend Setup

```bash
# Install development dependencies
pip install -r backend/requirements-dev.txt

# Set up pre-commit hooks
pre-commit install --hook-type pre-commit --hook-type commit-msg

# Copy environment template
cp backend/.env.example backend/.env
# Edit backend/.env with your configuration

# Run database migrations
cd backend
alembic upgrade head
cd ..

# Start development server
uvicorn backend.app.main:app --reload
```

#### Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

#### Docker Setup (Recommended)

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f
```

## Code Quality

### Pre-commit Hooks

We use pre-commit hooks to ensure code quality. They will run automatically on every commit.

**Setup:**
```bash
pip install pre-commit
pre-commit install --hook-type pre-commit --hook-type commit-msg
```

See [PRE_COMMIT_SETUP.md](PRE_COMMIT_SETUP.md) for detailed instructions.

### Python Code Style

- **Formatter**: [black](https://black.readthedocs.io/) (line length: 100)
- **Import sorting**: [isort](https://pycqa.github.io/isort/) (black profile)
- **Linting**: [flake8](https://flake8.pycqa.org/)
- **Type checking**: [mypy](http://mypy-lang.org/)

```bash
# Format code
black backend/app/
isort backend/app/

# Run linter
flake8 backend/app/

# Type checking
mypy backend/app/
```

### Frontend Code Style

```bash
cd frontend
npm run lint
```

## Commit Message Guidelines

We follow [Conventional Commits](https://www.conventionalcommits.org/) specification. This is enforced by pre-commit hooks.

### Format

```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

### Types

- **feat**: New feature
- **fix**: Bug fix
- **docs**: Documentation changes
- **style**: Code style changes (formatting, missing semicolons, etc.)
- **refactor**: Code refactoring (no functional changes)
- **perf**: Performance improvements
- **test**: Adding or updating tests
- **build**: Build system changes
- **ci**: CI/CD changes
- **chore**: Maintenance tasks

### Examples

```bash
# Simple feature
git commit -m "feat: add OAuth integration for Strava"

# Bug fix with scope
git commit -m "fix(frontend): correct activity display formatting"

# Breaking change
git commit -m "feat!: redesign API authentication

BREAKING CHANGE: Previous token-based auth is no longer supported.
Migrate to OAuth2 flow."
```

## Testing

### Backend Tests

```bash
# Run all tests
cd backend
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/test_sync_service.py

# Run specific test
pytest tests/test_sync_service.py::test_sync_activity
```

### Frontend Tests

```bash
cd frontend
npm test
```

### Writing Tests

- Write tests for all new features
- Maintain or improve code coverage
- Use descriptive test names
- Follow AAA pattern (Arrange, Act, Assert)

Example:
```python
def test_sync_activity_success():
    # Arrange
    activity = create_test_activity()
    service = SyncService()

    # Act
    result = service.sync_activity(activity)

    # Assert
    assert result.success is True
    assert result.activity_id is not None
```

## Pull Request Process

### Before Submitting

1. ✅ Ensure all tests pass
2. ✅ Run pre-commit hooks: `pre-commit run --all-files`
3. ✅ Update documentation if needed
4. ✅ Add tests for new features
5. ✅ Follow commit message conventions
6. ✅ Rebase on latest main branch

### Submitting

1. **Push your branch** to your fork:
   ```bash
   git push origin feat/your-feature-name
   ```

2. **Open a Pull Request** on GitHub with:
   - Clear title following conventional commit format
   - Description of changes
   - Link to related issues
   - Screenshots (if UI changes)
   - Test results

3. **PR Template:**
   ```markdown
   ## Description
   Brief description of changes

   ## Type of Change
   - [ ] Bug fix
   - [ ] New feature
   - [ ] Breaking change
   - [ ] Documentation update

   ## Testing
   - [ ] Tests pass locally
   - [ ] Added new tests
   - [ ] Updated documentation

   ## Screenshots (if applicable)

   ## Related Issues
   Closes #123
   ```

### Review Process

1. Maintainers will review your PR
2. Address any requested changes
3. Once approved, your PR will be merged
4. Your contribution will be included in the next release!

## Branching Strategy

- `main` - Production-ready code
- `feat/*` - New features
- `fix/*` - Bug fixes
- `docs/*` - Documentation updates
- `refactor/*` - Code refactoring
- `test/*` - Test additions/updates

## Release Process

We use semantic versioning and automated releases:

1. Changes are merged to `main`
2. Maintainer creates a version tag:
   ```bash
   git tag v1.2.3
   git push origin v1.2.3
   ```
3. GitHub Actions automatically:
   - Generates changelog
   - Creates GitHub release
   - Builds and publishes Docker images

## Security

### Reporting Vulnerabilities

**Do not** open public issues for security vulnerabilities.

Instead, email: [your-security-email@example.com]

### Security Guidelines

- Never commit secrets or credentials
- Use environment variables for sensitive data
- Run `detect-secrets` before committing
- Follow OWASP security best practices
- Keep dependencies up to date

## Documentation

### Code Documentation

- Add docstrings to all public functions/classes
- Use type hints
- Keep comments clear and concise
- Update README for major features

Example:
```python
def sync_activity(
    activity_id: str,
    user_id: int,
    force: bool = False
) -> SyncResult:
    """
    Sync a Strava activity to Garmin Connect.

    Args:
        activity_id: Strava activity ID
        user_id: User database ID
        force: Force sync even if already synced

    Returns:
        SyncResult with status and details

    Raises:
        SyncError: If sync fails
    """
    pass
```

### README Updates

Update ../README.md if you:
- Add new features
- Change configuration options
- Modify setup process
- Add dependencies

## Project Structure

```
strava-garmin-bridge/
├── backend/                 # Backend application
│   ├── app/                 # FastAPI application
│   │   ├── models/          # Database models
│   │   ├── routes/          # API routes
│   │   ├── services/        # Business logic
│   │   ├── tasks/           # Celery tasks
│   │   └── utils/           # Utilities
│   ├── migrations/          # Database migrations
│   └── tests/               # Backend tests
├── frontend/                # React frontend
│   └── src/                 # Source code
├── .github/                 # GitHub Actions
└── docs/                    # Documentation
```

## Getting Help

- **Documentation**: Check ../README.md and ./
- **Issues**: Browse existing GitHub issues
- **Discussions**: Start a GitHub discussion
- **Chat**: [Your chat platform, if any]

## Code of Conduct

### Our Pledge

We pledge to make participation in our project a harassment-free experience for everyone.

### Our Standards

- Using welcoming and inclusive language
- Being respectful of differing viewpoints
- Gracefully accepting constructive criticism
- Focusing on what is best for the community

### Enforcement

Report unacceptable behavior to: [your-email@example.com]

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

## Recognition

Contributors will be recognized in:
- GitHub contributors page
- Release notes

Thank you for contributing! 🎉
