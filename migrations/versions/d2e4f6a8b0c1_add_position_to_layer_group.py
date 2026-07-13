"""add position to layer group

Revision ID: d2e4f6a8b0c1
Revises: c5e4b7a91d32
Create Date: 2026-07-13
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d2e4f6a8b0c1"
down_revision: Union[str, None] = "c5e4b7a91d32"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "layer_group",
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("layer_group", "position")
