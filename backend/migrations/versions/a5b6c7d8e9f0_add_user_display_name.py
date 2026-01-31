"""add user profile fields (username, first_name, last_name)

Revision ID: a5b6c7d8e9f0
Revises: f4e5a6b7c8d9
Create Date: 2026-01-31

"""
from alembic import op
import sqlalchemy as sa


revision = "a5b6c7d8e9f0"
down_revision = "f4e5a6b7c8d9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("username", sa.String(64), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("first_name", sa.String(255), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("last_name", sa.String(255), nullable=True),
    )
    op.create_index(op.f("ix_users_username"), "users", ["username"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_users_username"), table_name="users")
    op.drop_column("users", "last_name")
    op.drop_column("users", "first_name")
    op.drop_column("users", "username")
