"""add token family index to auth sessions

Revision ID: c0ee884a3a30
Revises: b7c9d1e4f2a6
Create Date: 2026-08-29 23:30:15.868748

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "c0ee884a3a30"
down_revision: Union[str, Sequence[str], None] = "b7c9d1e4f2a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the missing token family index."""
    op.create_index(
        "ix_auth_sessions_token_family_id",
        "auth_sessions",
        ["token_family_id"],
        unique=False,
    )


def downgrade() -> None:
    """Remove the token family index."""
    op.drop_index(
        "ix_auth_sessions_token_family_id",
        table_name="auth_sessions",
    )