from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '9d3a0b6e4c21'
down_revision: Union[str, None] = '80ddb63ecc01'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        '''
        CREATE TABLE IF NOT EXISTS layer_group (
            id UUID PRIMARY KEY,
            created_at TIMESTAMP NULL,
            updated_at TIMESTAMP NULL,
            deleted_at TIMESTAMP NULL,
            name VARCHAR NOT NULL,
            layer_group_id UUID NULL REFERENCES layer_group(id)
        )
        '''
    )
    op.execute('CREATE INDEX IF NOT EXISTS ix_layer_group_name ON layer_group (name)')

    op.execute(
        '''
        CREATE TABLE IF NOT EXISTS "Layer" (
            id UUID PRIMARY KEY,
            created_at TIMESTAMP NULL,
            updated_at TIMESTAMP NULL,
            deleted_at TIMESTAMP NULL,
            name VARCHAR NOT NULL,
            subtitle VARCHAR NOT NULL,
            path_icon VARCHAR NOT NULL,
            path VARCHAR NOT NULL,
            activated BOOLEAN NOT NULL DEFAULT FALSE,
            layer_group_id UUID NOT NULL REFERENCES layer_group(id)
        )
        '''
    )
    op.execute('CREATE INDEX IF NOT EXISTS "ix_Layer_name" ON "Layer" (name)')

    op.create_table(
        'admin_analytics_event',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', postgresql.TIMESTAMP(), nullable=True),
        sa.Column('updated_at', postgresql.TIMESTAMP(), nullable=True),
        sa.Column('deleted_at', postgresql.TIMESTAMP(), nullable=True),
        sa.Column('domain', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('event_type', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('label', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('occurred_at', postgresql.TIMESTAMP(), nullable=False),
        sa.Column('actor_user_id', sa.UUID(), nullable=True),
        sa.Column('actor_name', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('target_type', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('target_id', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('status', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('endpoint_key', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('method', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('status_code', sa.Integer(), nullable=True),
        sa.Column('latency_ms', sa.Integer(), nullable=True),
        sa.Column('file_id', sa.UUID(), nullable=True),
        sa.Column('layer_id', sa.UUID(), nullable=True),
        sa.Column('metadata', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(['actor_user_id'], ['Users.id']),
        sa.ForeignKeyConstraint(['file_id'], ['PDF_Files.id']),
        sa.ForeignKeyConstraint(['layer_id'], ['Layer.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('id'),
    )
    op.create_index(op.f('ix_admin_analytics_event_actor_user_id'), 'admin_analytics_event', ['actor_user_id'], unique=False)
    op.create_index(op.f('ix_admin_analytics_event_deleted_at'), 'admin_analytics_event', ['deleted_at'], unique=False)
    op.create_index(op.f('ix_admin_analytics_event_domain'), 'admin_analytics_event', ['domain'], unique=False)
    op.create_index(op.f('ix_admin_analytics_event_endpoint_key'), 'admin_analytics_event', ['endpoint_key'], unique=False)
    op.create_index(op.f('ix_admin_analytics_event_event_type'), 'admin_analytics_event', ['event_type'], unique=False)
    op.create_index(op.f('ix_admin_analytics_event_file_id'), 'admin_analytics_event', ['file_id'], unique=False)
    op.create_index(op.f('ix_admin_analytics_event_layer_id'), 'admin_analytics_event', ['layer_id'], unique=False)
    op.create_index(op.f('ix_admin_analytics_event_occurred_at'), 'admin_analytics_event', ['occurred_at'], unique=False)
    op.create_index(op.f('ix_admin_analytics_event_status'), 'admin_analytics_event', ['status'], unique=False)
    op.create_index(op.f('ix_admin_analytics_event_status_code'), 'admin_analytics_event', ['status_code'], unique=False)
    op.create_index(op.f('ix_admin_analytics_event_target_id'), 'admin_analytics_event', ['target_id'], unique=False)
    op.create_index(op.f('ix_admin_analytics_event_target_type'), 'admin_analytics_event', ['target_type'], unique=False)

    op.create_table(
        'admin_analytics_export',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', postgresql.TIMESTAMP(), nullable=True),
        sa.Column('updated_at', postgresql.TIMESTAMP(), nullable=True),
        sa.Column('deleted_at', postgresql.TIMESTAMP(), nullable=True),
        sa.Column('domain', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('format', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('status', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('name', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('path', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('content_type', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('generated_at', postgresql.TIMESTAMP(), nullable=True),
        sa.Column('expires_at', postgresql.TIMESTAMP(), nullable=True),
        sa.Column('detail', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('filters', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('columns', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('admin_analytics_export')

    op.drop_index(op.f('ix_admin_analytics_event_target_type'), table_name='admin_analytics_event')
    op.drop_index(op.f('ix_admin_analytics_event_target_id'), table_name='admin_analytics_event')
    op.drop_index(op.f('ix_admin_analytics_event_status_code'), table_name='admin_analytics_event')
    op.drop_index(op.f('ix_admin_analytics_event_status'), table_name='admin_analytics_event')
    op.drop_index(op.f('ix_admin_analytics_event_occurred_at'), table_name='admin_analytics_event')
    op.drop_index(op.f('ix_admin_analytics_event_layer_id'), table_name='admin_analytics_event')
    op.drop_index(op.f('ix_admin_analytics_event_file_id'), table_name='admin_analytics_event')
    op.drop_index(op.f('ix_admin_analytics_event_event_type'), table_name='admin_analytics_event')
    op.drop_index(op.f('ix_admin_analytics_event_endpoint_key'), table_name='admin_analytics_event')
    op.drop_index(op.f('ix_admin_analytics_event_domain'), table_name='admin_analytics_event')
    op.drop_index(op.f('ix_admin_analytics_event_deleted_at'), table_name='admin_analytics_event')
    op.drop_index(op.f('ix_admin_analytics_event_actor_user_id'), table_name='admin_analytics_event')
    op.drop_table('admin_analytics_event')