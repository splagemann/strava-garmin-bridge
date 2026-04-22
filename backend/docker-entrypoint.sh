#!/bin/bash
set -e

echo "Starting Strava-Garmin Sync Bridge backend..."

run_migrations="${RUN_MIGRATIONS:-true}"

# Extract database connection details from DATABASE_URL
# Format: postgresql://user:password@host:port/dbname
if [ -n "$DATABASE_URL" ]; then
    # Extract components using parameter expansion and sed
    DB_USER=$(echo "$DATABASE_URL" | sed -n 's/.*:\/\/\([^:]*\):.*/\1/p')
    DB_PASS=$(echo "$DATABASE_URL" | sed -n 's/.*:\/\/[^:]*:\([^@]*\)@.*/\1/p')
    DB_HOST=$(echo "$DATABASE_URL" | sed -n 's/.*@\([^:\/]*\).*/\1/p')
    DB_NAME=$(echo "$DATABASE_URL" | sed -n 's/.*\/\([^?]*\).*/\1/p')

    echo "Waiting for PostgreSQL at $DB_HOST to be ready..."

    # Wait for PostgreSQL to be ready (with timeout)
    max_attempts=30
    attempt=0
    until PGPASSWORD="$DB_PASS" psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -c '\q' 2>/dev/null; do
        attempt=$((attempt + 1))
        if [ $attempt -ge $max_attempts ]; then
            echo "ERROR: PostgreSQL did not become ready in time"
            exit 1
        fi
        echo "PostgreSQL is unavailable - sleeping (attempt $attempt/$max_attempts)"
        sleep 2
    done

    if [ "$run_migrations" = "true" ]; then
        echo "PostgreSQL is up - running database migrations..."
        alembic upgrade head
        echo "Migrations completed successfully!"
    else
        echo "PostgreSQL is up - skipping database migrations (RUN_MIGRATIONS=$run_migrations)"
    fi
else
    echo "WARNING: DATABASE_URL not set, skipping database wait and migrations"
fi

# Execute the main command
exec "$@"
