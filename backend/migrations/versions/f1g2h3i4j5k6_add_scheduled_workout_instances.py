"""add_scheduled_workout_instances

Revision ID: f1g2h3i4j5k6
Revises: e1f2a3b4c5d6
Create Date: 2026-04-03 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = "f1g2h3i4j5k6"
down_revision = "e1f2a3b4c5d6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scheduled_workout_instances",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("workout_id", sa.String(), nullable=False),
        sa.Column("scheduled_date", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id", "workout_id", "scheduled_date", name="uq_user_workout_date"
        ),
    )
    op.create_index(
        op.f("ix_scheduled_workout_instances_id"),
        "scheduled_workout_instances",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_scheduled_workout_instances_user_id"),
        "scheduled_workout_instances",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_scheduled_workout_instances_scheduled_date"),
        "scheduled_workout_instances",
        ["scheduled_date"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_scheduled_workout_instances_scheduled_date"),
        table_name="scheduled_workout_instances",
    )
    op.drop_index(
        op.f("ix_scheduled_workout_instances_user_id"),
        table_name="scheduled_workout_instances",
    )
    op.drop_index(
        op.f("ix_scheduled_workout_instances_id"),
        table_name="scheduled_workout_instances",
    )
    op.drop_table("scheduled_workout_instances")
