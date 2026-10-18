"""add token family to auth sessions

Revision ID: b7c9d1e4f2a6
Revises: dd14c7d59501
"""

from uuid import uuid4

from alembic import op
import sqlalchemy as sa


revision = "b7c9d1e4f2a6"
down_revision = "dd14c7d59501"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "auth_sessions",
        sa.Column(
            "token_family_id",
            sa.Uuid(),
            nullable=True,
        ),
    )

    connection = op.get_bind()

    rows = connection.execute(
        sa.text(
            """
            SELECT id
            FROM auth_sessions
            WHERE token_family_id IS NULL
            """
        )
    ).fetchall()

    for row in rows:
        connection.execute(
            sa.text(
                """
                UPDATE auth_sessions
                SET token_family_id = :token_family_id
                WHERE id = :id
                """
            ),
            {
                "token_family_id": uuid4(),
                "id": row.id,
            },
        )

    op.alter_column(
        "auth_sessions",
        "token_family_id",
        nullable=False,
    )


def downgrade() -> None:
    op.drop_column(
        "auth_sessions",
        "token_family_id",
    )