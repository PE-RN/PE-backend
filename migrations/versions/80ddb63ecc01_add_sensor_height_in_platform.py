from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel

# revision identifiers, used by Alembic.
revision: str = '80ddb63ecc01'
down_revision: Union[str, None] = 'b630dcf00361'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('platform',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('name', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('sensor_height', sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('id')
    )

    op.create_index(op.f('ix_platform_name'), 'platform', ['name'], unique=True)

    op.create_table('qualified_data',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('dt', sa.DateTime(), nullable=False),
        sa.Column('m_temp', sa.Float(), nullable=False),
        sa.Column('m_pres', sa.Float(), nullable=False),
        sa.Column('m_wspd', sa.Float(), nullable=False),
        sa.Column('m_wdir', sa.Float(), nullable=False),
        sa.Column('height', sa.Integer(), nullable=False),
        sa.Column('h_spd', sa.Float(), nullable=False),
        sa.Column('ti', sa.Float(), nullable=False),
        sa.Column('wdir', sa.Float(), nullable=False),
        sa.Column('plat_id', sqlmodel.sql.sqltypes.GUID(), nullable=False),
        sa.ForeignKeyConstraint(['plat_id'], ['platform.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('dt', 'plat_id', 'height', name='uq_qualified_data_datetime_plat_id_height'),
        sa.UniqueConstraint('id')
    )

    op.create_index(op.f('ix_qualified_data_dt'), 'qualified_data', ['dt'], unique=False)
    op.create_index(op.f('ix_qualified_data_h_spd'), 'qualified_data', ['h_spd'], unique=False)
    op.create_index(op.f('ix_qualified_data_height'), 'qualified_data', ['height'], unique=False)
    op.create_index(op.f('ix_qualified_data_plat_id'), 'qualified_data', ['plat_id'], unique=False)
    op.create_index(op.f('ix_qualified_data_wdir'), 'qualified_data', ['wdir'], unique=False)



def downgrade() -> None:
    op.drop_index(op.f('ix_qualified_data_plat_id'), table_name='qualified_data')
    op.drop_index(op.f('ix_qualified_data_height'), table_name='qualified_data')
    op.drop_index(op.f('ix_qualified_data_h_spd'), table_name='qualified_data')
    op.drop_index(op.f('ix_qualified_data_dt'), table_name='qualified_data')
    op.drop_index(op.f('ix_qualified_data_wdir'), table_name='qualified_data')
    op.drop_table('qualified_data')

    op.drop_index(op.f('ix_platform_name'), table_name='platform')
    op.drop_table('platform')
