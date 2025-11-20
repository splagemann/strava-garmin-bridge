"""add_filter_field_to_activity_filters

Revision ID: 0440a8a49743
Revises: 682c5c77beda
Create Date: 2025-11-20 21:50:48.118429

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0440a8a49743'
down_revision = '682c5c77beda'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add filter_field column with default value 'name'
    op.add_column('activity_filters', sa.Column('filter_field', sa.String(), nullable=False, server_default='name'))


def downgrade() -> None:
    # Remove filter_field column
    op.drop_column('activity_filters', 'filter_field')
