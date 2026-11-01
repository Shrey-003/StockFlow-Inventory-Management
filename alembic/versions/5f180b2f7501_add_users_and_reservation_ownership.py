"""add users and reservation ownership

Revision ID: 5f180b2f7501
Revises: f49feedbdf32
Create Date: 2026-10-31 15:34:47.766247
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "5f180b2f7501"
down_revision: Union[str, Sequence[str], None] = "f49feedbdf32"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column(
            "role",
            sa.String(length=20),
            server_default="staff",
            nullable=False,
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "role IN ('admin', 'staff')",
            name="ck_users_role_valid",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("username"),
    )

    op.add_column(
        "reservations",
        sa.Column("user_id", sa.Integer(), nullable=True),
    )

    op.create_index(
        "ix_reservations_user_id",
        "reservations",
        ["user_id"],
        unique=False,
    )

    op.create_foreign_key(
        "fk_reservations_user_id_users",
        "reservations",
        "users",
        ["user_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_reservations_user_id_users",
        "reservations",
        type_="foreignkey",
    )

    op.drop_index(
        "ix_reservations_user_id",
        table_name="reservations",
    )

    op.drop_column("reservations", "user_id")
    op.drop_table("users")
