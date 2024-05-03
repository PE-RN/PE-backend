import subprocess

import geopandas
from sqlalchemy import MetaData, Table
from sqlalchemy.orm import Session
from sqlalchemy import MetaData, Table, text
from sqlalchemy.orm import Session
from schemas.geojson import GeoJSON
from rasterio.io import MemoryFile
import geopandas
import subprocess


class GeoRepository:

    def __init__(self, db: Session):
        self.db = db

    async def upload_polygon(
        self,
        polygon: geopandas.GeoDataFrame,
        table_name: str,
        increment: bool = True,
        new_columns: list = None
    ) -> None:

        if new_columns:
            polygon = [{**element, **new_columns} for element in polygon]

        engine = self.db.bind
        if_exists_option = 'append' if increment else 'replace'
        polygon.to_postgis(table_name, engine, if_exists=if_exists_option)

    async def upload_raster(
        self,
        raster_path: str,
        table_name: str,
        srid: int,
        increment: bool = True,
        new_columns: list = None
    ) -> None:

        # Drop the previous table if isnt to increment
        if not increment:
            drop_table_command = f"DROP TABLE IF EXISTS {table_name};"
            self.db.execute(drop_table_command)
            self.db.commit()

        # Upload the raster
        raster2pgsql_command = f'raster2pgsql -s {srid} -I -C -M {raster_path} {table_name}'
        output = subprocess.run(raster2pgsql_command, shell=True, capture_output=True, text=True)
        sql_statements = output.stdout

        self.db.execute(sql_statements)
        self.db.commit()

        if (not new_columns):
            return

        # Add the new columns to the new rows
        metadata = MetaData(bind=self.db.bind)
        raster_table = Table(table_name, metadata, autoload=True)
        raster_table_update = raster_table.update()

        first_column = next(iter(new_columns))
        raster_table_update.where(getattr(raster_table.c, first_column) == None)
        raster_table_update.values({column: value for column, value in new_columns.items()})

        self.db.execute(raster_table_update)
        self.db.commit()

    async def get_polygon(self, table_name) -> GeoJSON:

        polygon = geopandas.read_postgis(f'select * from {table_name}', geom_col='geometry', con=self.db.bind)
        return polygon.to_json()

    async def get_raster(self, table_name) -> Geometry:

        try:
            sql_query = f"SELECT ST_AsGDALRaster(rast, 'PNG') AS rast_data FROM {table_name} WHERE ST_Intersects(rast, ST_TileEnvelope(9, 205, 264));"
            result = self.db.execute(text(sql_query))
            raster_datas = result.fetchall()
            raster = b''

            all_png_data = []
            for raster_data in raster_datas:
                all_png_data.append(raster_data[0])

            complete_png_data = b''.join(all_png_data)
            return raster_datas
        except Exception as e:
            print(f'EROOOOOO {e}')

    async def validade_geofile(self, table_name) -> list:
        return self.db.query(Geodata).filter(Geodata.name == table_name).with_entities(Geodata.name, Geodata.geotype).first()
