"""add workout schedules

Revision ID: e1f2a3b4c5d6
Revises: b5f902b08422
Create Date: 2026-04-03 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa

revision = "e1f2a3b4c5d6"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workout_schedules",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("workout_id", sa.String(), nullable=False),
        sa.Column("workout_name", sa.String(), nullable=False),
        sa.Column("days_of_week", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_workout_schedules_id", "workout_schedules", ["id"], unique=False)
    op.create_index("ix_workout_schedules_user_id", "workout_schedules", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_workout_schedules_user_id", table_name="workout_schedules")
    op.drop_index("ix_workout_schedules_id", table_name="workout_schedules")
    op.drop_table("workout_schedules")
