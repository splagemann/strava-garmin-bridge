"""add_uploaded_file_fields_to_sync_logs

Revision ID: a1b2c3d4e5f6
Revises: a5b6c7d8e9f0
Create Date: 2026-01-31 12:00:00.000000

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f6"
down_revision = "a5b6c7d8e9f0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add uploaded_file_path column (String type) - stores path to file on filesystem
    op.add_column(
        "sync_logs", sa.Column("uploaded_file_path", sa.String(length=255), nullable=True)
    )

    # Add uploaded_file_extension column (String type)
    op.add_column(
        "sync_logs", sa.Column("uploaded_file_extension", sa.String(length=10), nullable=True)
    )


def downgrade() -> None:
    # Remove the added columns
    op.drop_column("sync_logs", "uploaded_file_extension")
    op.drop_column("sync_logs", "uploaded_file_path")
