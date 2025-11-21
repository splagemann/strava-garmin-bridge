"""add_bidirectional_sync_support

Revision ID: b5f902b08422
Revises: 193bece946bd
Create Date: 2025-11-21 20:12:45.959391

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b5f902b08422'
down_revision = '193bece946bd'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add sync_direction column with default value for existing records
    op.add_column('sync_logs', sa.Column('sync_direction', sa.String(), nullable=False, server_default='strava_to_garmin'))

    # Add source_activity_id column (will store either Strava ID or Garmin ID based on direction)
    op.add_column('sync_logs', sa.Column('source_activity_id', sa.String(), nullable=True))

    # Add target_activity_id column (stores the result ID from target platform)
    op.add_column('sync_logs', sa.Column('target_activity_id', sa.String(), nullable=True))

    # Migrate existing data: set source_activity_id from strava_activity_id for existing records
    op.execute("UPDATE sync_logs SET source_activity_id = strava_activity_id WHERE source_activity_id IS NULL")

    # Migrate existing data: set target_activity_id from garmin_activity_id for existing records
    op.execute("UPDATE sync_logs SET target_activity_id = garmin_activity_id WHERE target_activity_id IS NULL")

    # Make source_activity_id non-nullable after migration
    op.alter_column('sync_logs', 'source_activity_id', nullable=False)

    # Add index on source_activity_id for efficient lookup
    op.create_index(op.f('ix_sync_logs_source_activity_id'), 'sync_logs', ['source_activity_id'], unique=False)

    # Add index on sync_direction for filtering
    op.create_index(op.f('ix_sync_logs_sync_direction'), 'sync_logs', ['sync_direction'], unique=False)

    # Add composite index on (user_id, sync_direction, source_activity_id) for duplicate checking
    op.create_index('ix_sync_logs_user_direction_source', 'sync_logs', ['user_id', 'sync_direction', 'source_activity_id'], unique=False)


def downgrade() -> None:
    # Drop indexes
    op.drop_index('ix_sync_logs_user_direction_source', table_name='sync_logs')
    op.drop_index(op.f('ix_sync_logs_sync_direction'), table_name='sync_logs')
    op.drop_index(op.f('ix_sync_logs_source_activity_id'), table_name='sync_logs')

    # Drop columns
    op.drop_column('sync_logs', 'target_activity_id')
    op.drop_column('sync_logs', 'source_activity_id')
    op.drop_column('sync_logs', 'sync_direction')
