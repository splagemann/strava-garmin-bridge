"""add_debug_fields_to_sync_logs

Revision ID: 193bece946bd
Revises: 0440a8a49743
Create Date: 2025-11-20 22:14:17.763612

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = '193bece946bd'
down_revision = '0440a8a49743'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add strava_data column (JSON type)
    op.add_column('sync_logs', sa.Column('strava_data', postgresql.JSON(astext_type=sa.Text()), nullable=True))

    # Add gpx_data column (Text type)
    op.add_column('sync_logs', sa.Column('gpx_data', sa.Text(), nullable=True))


def downgrade() -> None:
    # Remove the added columns
    op.drop_column('sync_logs', 'gpx_data')
    op.drop_column('sync_logs', 'strava_data')
