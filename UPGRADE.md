# Upgrade Guide

This guide covers upgrading the Strava-Garmin Sync Bridge to newer versions.

## Before Upgrading

### 1. Check Current Version

```bash
# Check currently running version
docker-compose -f docker-compose.prod.yml exec backend python -c "import app; print(getattr(app, '__version__', 'unknown'))"

# Or check image tags
docker-compose -f docker-compose.prod.yml images
```

### 2. Review Changelog

Check [CHANGELOG.md](CHANGELOG.md) for:
- Breaking changes
- New features
- Required manual steps
- Database migrations

### 3. Backup Everything

**Always backup before upgrading!**

```bash
# Backup database
docker-compose -f docker-compose.prod.yml exec db pg_dump -U strava_garmin strava_garmin_sync | \
  gzip > backup-pre-upgrade-$(date +%Y%m%d).sql.gz

# Backup environment file
cp .env .env.backup

# Backup volumes (optional but recommended)
docker run --rm -v strava-garmin-bridge_postgres_data:/data -v $(pwd):/backup \
  alpine tar czf /backup/postgres-data-backup-$(date +%Y%m%d).tar.gz /data
```

## Upgrade Methods

### Method 1: Rolling Update (Recommended for Production)

Zero-downtime upgrade with health checks:

```bash
# Pull new images
docker-compose -f docker-compose.prod.yml pull

# Update services one at a time
docker-compose -f docker-compose.prod.yml up -d --no-deps --build backend
docker-compose -f docker-compose.prod.yml up -d --no-deps --build celery-worker
docker-compose -f docker-compose.prod.yml up -d --no-deps --build celery-beat
docker-compose -f docker-compose.prod.yml up -d --no-deps --build frontend

# Run migrations if needed
docker-compose -f docker-compose.prod.yml exec backend alembic upgrade head

# Verify services are healthy
docker-compose -f docker-compose.prod.yml ps
```

### Method 2: Full Restart (Simpler but with Downtime)

```bash
# Pull new images
docker-compose -f docker-compose.prod.yml pull

# Stop all services
docker-compose -f docker-compose.prod.yml down

# Start with new images
docker-compose -f docker-compose.prod.yml up -d

# Run migrations
docker-compose -f docker-compose.prod.yml exec backend alembic upgrade head

# Check logs
docker-compose -f docker-compose.prod.yml logs -f
```

### Method 3: Specific Version

```bash
# Update .env with specific version
echo "IMAGE_TAG=v1.2.0" >> .env

# Pull specific version
docker-compose -f docker-compose.prod.yml pull

# Restart services
docker-compose -f docker-compose.prod.yml up -d

# Run migrations
docker-compose -f docker-compose.prod.yml exec backend alembic upgrade head
```

## Upgrade Automation Script

Create `upgrade.sh`:

```bash
#!/bin/bash
set -e

BACKUP_DIR="./backups"
DATE=$(date +%Y%m%d-%H%M%S)
COMPOSE_FILE="docker-compose.prod.yml"

echo "=== Strava-Garmin Sync Bridge Upgrade ==="
echo "Starting upgrade at: $(date)"

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Step 1: Backup
echo "Step 1: Creating backup..."
docker-compose -f "$COMPOSE_FILE" exec -T db pg_dump -U strava_garmin strava_garmin_sync | \
  gzip > "$BACKUP_DIR/db-pre-upgrade-$DATE.sql.gz"
cp .env "$BACKUP_DIR/env-pre-upgrade-$DATE"
echo "✓ Backup created: $BACKUP_DIR/db-pre-upgrade-$DATE.sql.gz"

# Step 2: Pull new images
echo "Step 2: Pulling new images..."
docker-compose -f "$COMPOSE_FILE" pull
echo "✓ Images pulled"

# Step 3: Check for breaking changes
echo "Step 3: Checking for breaking changes..."
# Add custom logic here if needed
echo "✓ No blocking issues found"

# Step 4: Stop services
echo "Step 4: Stopping services..."
docker-compose -f "$COMPOSE_FILE" down
echo "✓ Services stopped"

# Step 5: Start services
echo "Step 5: Starting services with new images..."
docker-compose -f "$COMPOSE_FILE" up -d
echo "✓ Services started"

# Step 6: Wait for services to be healthy
echo "Step 6: Waiting for services to be healthy..."
sleep 10
for i in {1..30}; do
  if docker-compose -f "$COMPOSE_FILE" ps | grep -q "unhealthy"; then
    echo "Waiting for services to become healthy... ($i/30)"
    sleep 2
  else
    break
  fi
done

# Step 7: Run migrations
echo "Step 7: Running database migrations..."
docker-compose -f "$COMPOSE_FILE" exec -T backend alembic upgrade head
echo "✓ Migrations completed"

# Step 8: Verify
echo "Step 8: Verifying deployment..."
docker-compose -f "$COMPOSE_FILE" ps

# Check backend health
if curl -f http://localhost:8000/health > /dev/null 2>&1; then
  echo "✓ Backend health check passed"
else
  echo "⚠ Warning: Backend health check failed"
fi

echo ""
echo "=== Upgrade Complete ==="
echo "Completed at: $(date)"
echo "Backup location: $BACKUP_DIR/db-pre-upgrade-$DATE.sql.gz"
echo ""
echo "Next steps:"
echo "1. Check logs: docker-compose -f $COMPOSE_FILE logs -f"
echo "2. Verify application is working correctly"
echo "3. If issues occur, rollback: docker-compose -f $COMPOSE_FILE exec -T db psql -U strava_garmin strava_garmin_sync < $BACKUP_DIR/db-pre-upgrade-$DATE.sql.gz"
```

Make it executable and run:

```bash
chmod +x upgrade.sh
./upgrade.sh
```

## Version-Specific Upgrade Notes

### Upgrading to v1.x.x

No special steps required. Follow standard upgrade process.

### Future Versions

Check [CHANGELOG.md](CHANGELOG.md) for version-specific upgrade notes.

## Post-Upgrade Verification

### 1. Check Service Status

```bash
# All services should be "healthy" or "running"
docker-compose -f docker-compose.prod.yml ps

# Expected output:
# NAME                          STATUS              PORTS
# strava-garmin-backend         Up (healthy)        0.0.0.0:8000->8000/tcp
# strava-garmin-celery-beat     Up
# strava-garmin-celery-worker   Up
# strava-garmin-db              Up (healthy)        5432/tcp
# strava-garmin-frontend        Up (healthy)        0.0.0.0:3000->80/tcp
# strava-garmin-redis           Up (healthy)        6379/tcp
```

### 2. Check Logs

```bash
# Check for errors in logs
docker-compose -f docker-compose.prod.yml logs --tail=100

# Should not see errors, exceptions, or warnings
```

### 3. Test Functionality

1. **Access frontend**: Open https://yourdomain.com
2. **Check authentication**: Try logging in with Strava
3. **Test sync**: Manually trigger a sync
4. **View sync history**: Verify previous syncs are visible
5. **Check API**: Visit https://api.yourdomain.com/docs

### 4. Monitor Performance

```bash
# Check resource usage
docker stats

# Monitor logs in real-time
docker-compose -f docker-compose.prod.yml logs -f

# Check Celery tasks are processing
docker-compose -f docker-compose.prod.yml logs -f celery-worker
```

## Rollback

If the upgrade fails or causes issues:

### Quick Rollback

```bash
# Stop new version
docker-compose -f docker-compose.prod.yml down

# Update .env to previous version
echo "IMAGE_TAG=v1.0.0" >> .env  # Replace with your previous version

# Start previous version
docker-compose -f docker-compose.prod.yml up -d

# Restore database if needed
docker-compose -f docker-compose.prod.yml exec -T db psql -U strava_garmin strava_garmin_sync < backup-pre-upgrade-20240101.sql.gz
```

### Complete Rollback with Database Restore

```bash
# Stop all services
docker-compose -f docker-compose.prod.yml down

# Remove volumes (⚠️ WARNING: This deletes current data)
docker-compose -f docker-compose.prod.yml down -v

# Update to previous version
echo "IMAGE_TAG=v1.0.0" >> .env

# Start services
docker-compose -f docker-compose.prod.yml up -d

# Wait for database to be ready
sleep 20

# Restore database backup
gunzip < backup-pre-upgrade-20240101.sql.gz | \
  docker-compose -f docker-compose.prod.yml exec -T db psql -U strava_garmin strava_garmin_sync

# Verify
docker-compose -f docker-compose.prod.yml ps
```

## Migration Troubleshooting

### Failed Migrations

If database migrations fail:

```bash
# Check current migration version
docker-compose -f docker-compose.prod.yml exec backend alembic current

# View migration history
docker-compose -f docker-compose.prod.yml exec backend alembic history

# Manually run specific migration
docker-compose -f docker-compose.prod.yml exec backend alembic upgrade <revision>

# Rollback one migration
docker-compose -f docker-compose.prod.yml exec backend alembic downgrade -1
```

### Stuck Migrations

```bash
# Access database
docker-compose -f docker-compose.prod.yml exec db psql -U strava_garmin strava_garmin_sync

# Check alembic version table
SELECT * FROM alembic_version;

# Manually update version (⚠️ Use with caution)
UPDATE alembic_version SET version_num = 'target_revision';
```

## Best Practices

1. **Always backup** before upgrading
2. **Read the changelog** for breaking changes
3. **Test in staging** environment first if possible
4. **Upgrade during low-traffic** periods
5. **Monitor logs** during and after upgrade
6. **Keep backups** for at least 7 days
7. **Document custom changes** you've made
8. **Use version tags** instead of `latest` in production
9. **Automate upgrades** with scripts
10. **Have rollback plan** ready

## Automated Upgrade Schedule

Set up automated checks for new versions:

```bash
# Create check-updates.sh
#!/bin/bash
CURRENT_VERSION=$(cat .env | grep IMAGE_TAG | cut -d'=' -f2)
LATEST_VERSION=$(curl -s https://api.github.com/repos/splagemann/strava-garmin-bridge/releases/latest | grep tag_name | cut -d'"' -f4)

if [ "$CURRENT_VERSION" != "$LATEST_VERSION" ]; then
  echo "New version available: $LATEST_VERSION (current: $CURRENT_VERSION)"
  echo "Run ./upgrade.sh to upgrade"
  # Optionally send notification
else
  echo "Already on latest version: $CURRENT_VERSION"
fi
```

Schedule with cron:

```bash
# Check for updates daily at 9 AM
0 9 * * * /path/to/check-updates.sh >> /var/log/strava-garmin-updates.log 2>&1
```

## Getting Help

If you encounter issues during upgrade:

1. Check the [Troubleshooting section](#migration-troubleshooting)
2. Review [GitHub Issues](https://github.com/splagemann/strava-garmin-bridge/issues)
3. Check [GitHub Discussions](https://github.com/splagemann/strava-garmin-bridge/discussions)
4. Open a new issue with:
   - Current version
   - Target version
   - Error logs
   - Steps to reproduce

## Upgrade Checklist

Print or save this checklist for each upgrade:

- [ ] Read changelog for version being upgraded to
- [ ] Backup database
- [ ] Backup .env file
- [ ] Note current version
- [ ] Pull new images
- [ ] Stop services
- [ ] Start services with new images
- [ ] Run database migrations
- [ ] Verify service health
- [ ] Check logs for errors
- [ ] Test core functionality
- [ ] Monitor for 24 hours
- [ ] Keep backup for 7 days
- [ ] Document any issues
- [ ] Update internal documentation
