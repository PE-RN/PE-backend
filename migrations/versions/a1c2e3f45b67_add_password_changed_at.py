"""add password_changed_at to users

Revision ID: a1c2e3f45b67
Revises: f3c8a9d12b47
Create Date: 2026-05-15 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'a1c2e3f45b67'
down_revision = 'f3c8a9d12b47'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'Users',
        sa.Column('password_changed_at', sa.TIMESTAMP(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('Users', 'password_changed_at')
