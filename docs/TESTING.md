# Testing Guide

This document provides comprehensive information about the testing strategy and implementation for the Strava-Garmin Bridge application.

## Table of Contents

- [Overview](#overview)
- [Backend Testing](#backend-testing)
- [Frontend Testing](#frontend-testing)
- [Running Tests](#running-tests)
- [Test Coverage](#test-coverage)
- [CI/CD Integration](#cicd-integration)
- [Writing New Tests](#writing-new-tests)

## Overview

The project uses a comprehensive testing strategy covering:

- **Backend (Python/FastAPI)**: pytest with fixtures, mocking, and integration tests
- **Frontend (React/TypeScript)**: Vitest with React Testing Library
- **Coverage**: Aiming for 80%+ on critical paths

### Test Pyramid

1. **Unit Tests** (70%): Test individual functions, classes, and components
2. **Integration Tests** (20%): Test interactions between services and APIs
3. **E2E Tests** (10%): Test complete user workflows (future)

## Backend Testing

### Setup

Install test dependencies:

```bash
pip install -r backend/requirements-dev.txt
```

### Test Structure

```
backend/tests/
├── conftest.py              # Global fixtures and configuration
├── fixtures/
│   ├── activity_data.py     # Mock activity data factories
│   └── __init__.py
├── services/                # Service layer tests
│   ├── test_sync_service.py
│   ├── test_garmin_to_strava_sync_service.py
│   └── __init__.py
├── utils/                   # Utility function tests
│   ├── test_crypto.py
│   ├── test_jwt.py
│   ├── test_activity_converter.py
│   └── __init__.py
├── tasks/                   # Celery task tests
│   ├── test_sync_tasks.py
│   └── __init__.py
└── routes/                  # API endpoint tests
    ├── test_auth.py
    ├── test_sync.py
    ├── test_filters.py
    └── __init__.py
```

### Key Test Areas

#### 1. Service Layer Tests

**Sync Services** (`tests/services/`)
- Activity filtering logic (include/exclude patterns, regex)
- Duplicate detection (ping-pong prevention)
- Date format handling (ISO vs simple format from Garmin API)
- Error handling and retries

**Example:**
```python
def test_should_sync_activity_with_filters(test_db, test_user):
    """Test activity filtering with include/exclude patterns."""
    # Create include filter
    filter_rule = ActivityFilter(
        user_id=test_user.id,
        filter_type="include",
        filter_field="name",
        pattern="Morning",
        is_regex=False,
        active=True,
    )
    test_db.add(filter_rule)
    test_db.commit()

    sync_service = SyncService(test_db, test_user)
    assert sync_service.should_sync_activity("Morning Run") is True
    assert sync_service.should_sync_activity("Evening Run") is False
```

#### 2. Utility Tests

**Encryption** (`tests/utils/test_crypto.py`)
- Encrypt/decrypt roundtrip
- Unicode character handling
- Invalid data handling

**JWT** (`tests/utils/test_jwt.py`)
- Token creation and verification
- Expiration handling
- State token validation (OAuth CSRF protection)

**Activity Converter** (`tests/utils/test_activity_converter.py`)
- Strava type extraction (Pydantic format handling)
- FIT sport type mapping
- GPX conversion

#### 3. Task Tests

**Celery Tasks** (`tests/tasks/test_sync_tasks.py`)
- Individual activity sync
- Batch sync operations
- Retry logic with exponential backoff
- Error handling
- Polling task behavior

#### 4. API Tests

**Authentication** (`tests/routes/test_auth.py`)
- OAuth flow (Strava)
- Credential-based auth (Garmin)
- State validation

**Sync Endpoints** (`tests/routes/test_sync.py`)
- Manual sync triggers
- Batch operations
- Sync history
- Force sync parameter

**Filters** (`tests/routes/test_filters.py`)
- CRUD operations
- Filter validation
- Pattern matching

### Running Backend Tests

```bash
# Run all tests
cd backend
pytest

# Run with coverage
pytest --cov=app --cov-report=html --cov-report=term

# Run specific test file
pytest tests/services/test_sync_service.py

# Run specific test
pytest tests/services/test_sync_service.py::TestShouldSyncActivity::test_no_filters_syncs_all

# Run with verbose output
pytest -v

# Run with print statements
pytest -s

# Run tests in parallel (faster)
pytest -n auto
```

### Backend Testing Best Practices

1. **Use Fixtures**: Leverage pytest fixtures for common setup
2. **Mock External APIs**: Always mock Strava/Garmin API calls
3. **Use In-Memory DB**: Tests use SQLite in-memory for speed
4. **Test Error Cases**: Don't just test happy paths
5. **Check Side Effects**: Verify database changes, logs, etc.

## Frontend Testing

### Setup

Install test dependencies:

```bash
cd frontend
npm install
```

### Test Structure

```
frontend/src/
├── test/
│   ├── setup.ts             # Global test setup
│   ├── test-utils.tsx       # Custom render with providers
│   └── mockData/
│       ├── activities.ts    # Mock activity data
│       └── auth.ts          # Mock auth data
├── hooks/
│   └── __tests__/
│       ├── useAuth.test.ts
│       └── useSync.test.ts
└── components/
    └── __tests__/
        └── [component].test.tsx
```

### Key Test Areas

#### 1. Hook Tests

**useAuth** (`hooks/__tests__/useAuth.test.ts`)
- Loading states
- Authentication status
- Partial authentication (Strava only, Garmin only)
- Error handling

**useSync** (`hooks/__tests__/useSync.test.ts`)
- Manual sync triggering
- Force sync parameter
- Sync history fetching
- Error handling

#### 2. Component Tests

Components should test:
- Rendering with different props
- User interactions (clicks, form inputs)
- Conditional rendering
- Error states
- Loading states

### Running Frontend Tests

```bash
cd frontend

# Run all tests
npm test

# Run tests in watch mode
npm test -- --watch

# Run with UI (interactive)
npm run test:ui

# Run with coverage
npm run test:coverage

# Run specific test file
npm test -- hooks/__tests__/useAuth.test.ts
```

### Frontend Testing Best Practices

1. **Use Custom Render**: Import from `test-utils.tsx` for providers
2. **Mock API Calls**: Use MSW for API mocking (future)
3. **Test User Behavior**: Focus on what users see/do, not implementation
4. **Use Testing Library Queries**: Prefer `getByRole` over `getByTestId`
5. **Avoid Testing Implementation Details**: Test behavior, not state

## Test Coverage

### Coverage Goals

- **Critical Paths**: 90%+ (sync logic, filters, crypto)
- **Service Layer**: 85%+
- **Utilities**: 85%+
- **API Endpoints**: 75%+
- **Components**: 70%+

### Viewing Coverage Reports

**Backend:**
```bash
cd backend
pytest --cov=app --cov-report=html
open htmlcov/index.html
```

**Frontend:**
```bash
cd frontend
npm run test:coverage
open coverage/index.html
```

### Coverage Configuration

**Backend** (`pyproject.toml` or `.coveragerc`):
```ini
[coverage:run]
source = app
omit =
    */tests/*
    */migrations/*
    */__pycache__/*
```

**Frontend** (`vitest.config.ts`):
```typescript
coverage: {
  provider: 'v8',
  exclude: [
    'node_modules/',
    'src/test/',
    '**/*.config.*',
  ],
}
```

## CI/CD Integration

### GitHub Actions Example

Create `.github/workflows/test.yml`:

```yaml
name: Tests

on: [push, pull_request]

jobs:
  backend-tests:
    runs-on: ubuntu-latest

    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: postgres
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

      redis:
        image: redis:7
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -r backend/requirements.txt
          pip install -r backend/requirements-dev.txt

      - name: Run tests
        run: |
          cd backend
          pytest --cov=app --cov-report=xml
        env:
          DATABASE_URL: postgresql://postgres:postgres@localhost/test_db
          REDIS_URL: redis://localhost:6379/0

      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          file: ./coverage.xml

  frontend-tests:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v3

      - name: Set up Node.js
        uses: actions/setup-node@v3
        with:
          node-version: '20'

      - name: Install dependencies
        run: |
          cd frontend
          npm ci

      - name: Run tests
        run: |
          cd frontend
          npm run test:coverage

      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          file: ./frontend/coverage/coverage-final.json
```

## Writing New Tests

### Adding a Backend Test

1. **Choose Test Type**: Unit, integration, or E2E
2. **Create Test File**: Follow naming convention `test_*.py`
3. **Import Fixtures**: Use existing fixtures from `conftest.py`
4. **Write Test**: Follow AAA pattern (Arrange, Act, Assert)

Example:
```python
def test_new_feature(test_db, test_user):
    # Arrange
    service = MyService(test_db, test_user)
    input_data = {"key": "value"}

    # Act
    result = service.process(input_data)

    # Assert
    assert result["status"] == "success"
    assert result["data"]["key"] == "value"
```

### Adding a Frontend Test

1. **Create Test File**: Place next to component or in `__tests__/`
2. **Import Test Utils**: Use custom render from `test-utils.tsx`
3. **Mock Dependencies**: Mock API calls if needed
4. **Write Test**: Focus on user behavior

Example:
```typescript
import { render, screen, fireEvent } from '../../test/test-utils';
import { MyComponent } from '../MyComponent';

describe('MyComponent', () => {
  it('should handle button click', () => {
    render(<MyComponent />);

    const button = screen.getByRole('button', { name: /submit/i });
    fireEvent.click(button);

    expect(screen.getByText(/success/i)).toBeInTheDocument();
  });
});
```

## Test Data Management

### Backend Fixtures

Use factory functions for consistent test data:

```python
from tests.fixtures.activity_data import StravaActivityFactory

activity = StravaActivityFactory.create(
    activity_id=123,
    name="Test Activity",
    activity_type="Run"
)
```

### Frontend Mock Data

Import from mock data files:

```typescript
import { mockStravaActivity } from '../test/mockData/activities';

// Use in tests
const activity = mockStravaActivity;
```

## Debugging Tests

### Backend Debugging

```bash
# Run single test with debugger
pytest -s tests/services/test_sync_service.py::test_name

# Use pdb
import pdb; pdb.set_trace()

# Print database queries
pytest -v --log-cli-level=DEBUG
```

### Frontend Debugging

```bash
# Run in watch mode
npm test -- --watch

# Use debugger
debugger; // In test code

# View DOM structure
screen.debug(); // In test
```

## Common Issues

### Backend

**Issue**: Database connection errors
**Solution**: Ensure test database is properly configured in conftest.py

**Issue**: Hanging tests
**Solution**: Check for unclosed database sessions or background tasks

**Issue**: Import errors
**Solution**: Add `sys.path.insert(0, ...)` in conftest.py

### Frontend

**Issue**: "Cannot find module" errors
**Solution**: Check vitest.config.ts resolve.alias configuration

**Issue**: React hooks errors
**Solution**: Ensure component is wrapped with proper providers

**Issue**: Async test failures
**Solution**: Use waitFor() or act() for async operations

## Resources

- [pytest Documentation](https://docs.pytest.org/)
- [React Testing Library](https://testing-library.com/react)
- [Vitest Documentation](https://vitest.dev/)
- [FastAPI Testing](https://fastapi.tiangolo.com/tutorial/testing/)

## Contributing

When adding new features:

1. Write tests first (TDD approach recommended)
2. Aim for 80%+ coverage on new code
3. Run full test suite before committing
4. Update this documentation if adding new test patterns
