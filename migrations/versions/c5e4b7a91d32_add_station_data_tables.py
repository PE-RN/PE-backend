"""add station data tables

Revision ID: c5e4b7a91d32
Revises: a1c2e3f45b67
Create Date: 2026-05-20 00:00:00.000000

"""
from __future__ import annotations

import uuid as py_uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = 'c5e4b7a91d32'
down_revision = 'a1c2e3f45b67'
branch_labels = None
depends_on = None


DEFAULT_LIDAR_TYPE_ID = py_uuid.UUID('4d4d5324-6d92-4dc0-8d1b-56f0a785b8dd')
DEFAULT_SOLARIMETRIC_TYPE_ID = py_uuid.UUID('a53ed1ce-8e80-4d71-bfa4-3aa44da8ae31')


UUID_TYPE = postgresql.UUID(as_uuid=True)


def _inspect(bind):
    return sa.inspect(bind)


def _table_exists(inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def _column_names(inspector, table_name: str) -> set[str]:
    return {column['name'] for column in inspector.get_columns(table_name)}


def _index_exists(inspector, table_name: str, index_name: str) -> bool:
    return any(index['name'] == index_name for index in inspector.get_indexes(table_name))


def _foreign_key_exists(inspector, table_name: str, constrained_columns: list[str], referred_table: str) -> bool:
    for foreign_key in inspector.get_foreign_keys(table_name):
        if foreign_key.get('referred_table') != referred_table:
            continue
        if foreign_key.get('constrained_columns') == constrained_columns:
            return True
    return False


def _create_station_type_table() -> None:
    op.create_table(
        'station_type',
        sa.Column('id', UUID_TYPE, nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name', name='uq_station_type_name'),
    )


def _get_or_create_station_type_id(bind, name: str, default_id: py_uuid.UUID) -> py_uuid.UUID:
    existing_id = bind.execute(
        sa.text('SELECT id FROM station_type WHERE lower(name) = lower(:name) LIMIT 1'),
        {'name': name},
    ).scalar_one_or_none()
    if existing_id is not None:
        return existing_id

    bind.execute(
        sa.text('INSERT INTO station_type (id, name) VALUES (:id, :name)'),
        {'id': default_id, 'name': name},
    )
    return default_id


def _ensure_index(inspector, table_name: str, index_name: str, columns: list[str]) -> None:
    if not _index_exists(inspector, table_name, index_name):
        op.create_index(index_name, table_name, columns, unique=False)


def _ensure_data_station_table(bind) -> py_uuid.UUID:
    inspector = _inspect(bind)
    tables = set(inspector.get_table_names())

    if 'platform' in tables and 'data_station' not in tables:
        op.rename_table('platform', 'data_station')
        inspector = _inspect(bind)
        tables = set(inspector.get_table_names())

    if 'data_station' not in tables:
        op.create_table(
            'data_station',
            sa.Column('id', UUID_TYPE, nullable=False),
            sa.Column('name', sa.String(), nullable=False),
            sa.Column('sensor_height', sa.Float(), nullable=True),
            sa.Column('type', UUID_TYPE, nullable=False),
            sa.Column('layer_id', UUID_TYPE, nullable=True),
            sa.ForeignKeyConstraint(['layer_id'], ['Layer.id']),
            sa.ForeignKeyConstraint(['type'], ['station_type.id']),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('name', name='uq_data_station_name'),
        )
        inspector = _inspect(bind)
    else:
        columns = _column_names(inspector, 'data_station')
        if 'station_type' in columns and 'type' not in columns:
            op.alter_column(
                'data_station',
                'station_type',
                new_column_name='type',
                existing_type=UUID_TYPE,
                existing_nullable=True,
            )
            inspector = _inspect(bind)
            columns = _column_names(inspector, 'data_station')

        if 'type' not in columns:
            op.add_column('data_station', sa.Column('type', UUID_TYPE, nullable=True))
            inspector = _inspect(bind)
            columns = _column_names(inspector, 'data_station')

        if 'layer_id' not in columns:
            op.add_column('data_station', sa.Column('layer_id', UUID_TYPE, nullable=True))
            inspector = _inspect(bind)

    lidar_type_id = _get_or_create_station_type_id(bind, 'lidar', DEFAULT_LIDAR_TYPE_ID)
    _get_or_create_station_type_id(bind, 'solarimetric', DEFAULT_SOLARIMETRIC_TYPE_ID)

    bind.execute(
        sa.text('UPDATE data_station SET "type" = :station_type_id WHERE "type" IS NULL'),
        {'station_type_id': lidar_type_id},
    )

    inspector = _inspect(bind)
    if not _foreign_key_exists(inspector, 'data_station', ['type'], 'station_type'):
        op.create_foreign_key(
            'fk_data_station_type_station_type',
            'data_station',
            'station_type',
            ['type'],
            ['id'],
        )
        inspector = _inspect(bind)
    if not _foreign_key_exists(inspector, 'data_station', ['layer_id'], 'Layer'):
        op.create_foreign_key(
            'fk_data_station_layer_id_layer',
            'data_station',
            'Layer',
            ['layer_id'],
            ['id'],
        )
        inspector = _inspect(bind)

    _ensure_index(inspector, 'data_station', 'ix_data_station_type', ['type'])
    inspector = _inspect(bind)
    _ensure_index(inspector, 'data_station', 'ix_data_station_layer_id', ['layer_id'])

    op.alter_column('data_station', 'type', existing_type=UUID_TYPE, nullable=False)
    return lidar_type_id


def _ensure_lidar_station_data_table(bind) -> None:
    inspector = _inspect(bind)
    tables = set(inspector.get_table_names())

    if 'qualified_data' in tables and 'lidar_station_data' not in tables:
        op.rename_table('qualified_data', 'lidar_station_data')
        inspector = _inspect(bind)
        tables = set(inspector.get_table_names())

    if 'lidar_station_data' not in tables:
        op.create_table(
            'lidar_station_data',
            sa.Column('id', UUID_TYPE, nullable=False),
            sa.Column('dt', sa.DateTime(), nullable=False),
            sa.Column('m_temp', sa.Float(), nullable=False),
            sa.Column('m_pres', sa.Float(), nullable=False),
            sa.Column('m_wspd', sa.Float(), nullable=False),
            sa.Column('m_wdir', sa.Float(), nullable=False),
            sa.Column('height', sa.Integer(), nullable=False),
            sa.Column('h_spd', sa.Float(), nullable=False),
            sa.Column('wdir', sa.Float(), nullable=False),
            sa.Column('ti', sa.Float(), nullable=False),
            sa.Column('station_id', UUID_TYPE, nullable=False),
            sa.ForeignKeyConstraint(['station_id'], ['data_station.id']),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('dt', 'station_id', 'height', name='uq_lidar_station_data_datetime_station_id_height'),
        )
        inspector = _inspect(bind)
    else:
        columns = _column_names(inspector, 'lidar_station_data')
        if 'plat_id' in columns and 'station_id' not in columns:
            op.alter_column(
                'lidar_station_data',
                'plat_id',
                new_column_name='station_id',
                existing_type=UUID_TYPE,
                existing_nullable=False,
            )
            inspector = _inspect(bind)
            columns = _column_names(inspector, 'lidar_station_data')

        if 'station_id' not in columns:
            op.add_column('lidar_station_data', sa.Column('station_id', UUID_TYPE, nullable=True))
            inspector = _inspect(bind)

    if not _foreign_key_exists(inspector, 'lidar_station_data', ['station_id'], 'data_station'):
        op.create_foreign_key(
            'fk_lidar_station_data_station_id_data_station',
            'lidar_station_data',
            'data_station',
            ['station_id'],
            ['id'],
        )
        inspector = _inspect(bind)

    _ensure_index(inspector, 'lidar_station_data', 'ix_lidar_station_data_dt', ['dt'])
    inspector = _inspect(bind)
    _ensure_index(inspector, 'lidar_station_data', 'ix_lidar_station_data_station_id', ['station_id'])


def _ensure_solarimetric_station_table(bind) -> None:
    inspector = _inspect(bind)
    tables = set(inspector.get_table_names())

    if 'solar_station_data' in tables and 'solarimetric_stations' not in tables:
        op.rename_table('solar_station_data', 'solarimetric_stations')
        inspector = _inspect(bind)
        tables = set(inspector.get_table_names())

    if 'solarimetric_stations' not in tables:
        op.create_table(
            'solarimetric_stations',
            sa.Column('id', UUID_TYPE, nullable=False),
            sa.Column('dt', sa.DateTime(), nullable=False),
            sa.Column('ghi', sa.Float(), nullable=False),
            sa.Column('hum', sa.Float(), nullable=False),
            sa.Column('temp', sa.Float(), nullable=False),
            sa.Column('vel', sa.Float(), nullable=False),
            sa.Column('station_id', UUID_TYPE, nullable=False),
            sa.ForeignKeyConstraint(['station_id'], ['data_station.id']),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('dt', 'station_id', name='uq_solarimetric_stations_datetime_station_id'),
        )
        inspector = _inspect(bind)

    if not _foreign_key_exists(inspector, 'solarimetric_stations', ['station_id'], 'data_station'):
        op.create_foreign_key(
            'fk_solarimetric_stations_station_id_data_station',
            'solarimetric_stations',
            'data_station',
            ['station_id'],
            ['id'],
        )
        inspector = _inspect(bind)

    _ensure_index(inspector, 'solarimetric_stations', 'ix_solarimetric_stations_dt', ['dt'])
    inspector = _inspect(bind)
    _ensure_index(inspector, 'solarimetric_stations', 'ix_solarimetric_stations_station_id', ['station_id'])


def upgrade() -> None:
    bind = op.get_bind()
    inspector = _inspect(bind)

    if not _table_exists(inspector, 'station_type'):
        _create_station_type_table()

    _ensure_data_station_table(bind)
    _ensure_lidar_station_data_table(bind)
    _ensure_solarimetric_station_table(bind)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = _inspect(bind)
    tables = set(inspector.get_table_names())

    if 'solarimetric_stations' in tables and 'solar_station_data' not in tables:
        op.rename_table('solarimetric_stations', 'solar_station_data')
        inspector = _inspect(bind)
        tables = set(inspector.get_table_names())

    if 'lidar_station_data' in tables:
        columns = _column_names(inspector, 'lidar_station_data')
        if 'station_id' in columns and 'plat_id' not in columns:
            op.alter_column(
                'lidar_station_data',
                'station_id',
                new_column_name='plat_id',
                existing_type=UUID_TYPE,
                existing_nullable=False,
            )
            inspector = _inspect(bind)
            tables = set(inspector.get_table_names())
        if 'qualified_data' not in tables:
            op.rename_table('lidar_station_data', 'qualified_data')
            inspector = _inspect(bind)
            tables = set(inspector.get_table_names())

    if 'data_station' in tables:
        columns = _column_names(inspector, 'data_station')
        if 'type' in columns and 'station_type' not in columns:
            op.alter_column(
                'data_station',
                'type',
                new_column_name='station_type',
                existing_type=UUID_TYPE,
                existing_nullable=False,
            )
            inspector = _inspect(bind)
            tables = set(inspector.get_table_names())
        if 'platform' not in tables:
            op.rename_table('data_station', 'platform')
