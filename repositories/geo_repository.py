import os
import subprocess
import tempfile

import geopandas
from os import getenv
from osgeo import gdal
from osgeo.gdal import Dataset
from sqlalchemy import MetaData, Table, text
from sqlmodel.ext.asyncio.session import AsyncSession

from schemas.geojson import GeoJSON
from schemas.geometry import Geometry
from sql_app.models import Geodata
from sqlmodel import select


class GeoRepository:

    def __init__(self, db: AsyncSession):
        self.db = db

    def upload_polygon(self, polygon: geopandas.GeoDataFrame, table_name: str, increment: bool = True, new_columns: list = None):

        if new_columns:
            polygon = [{**element, **new_columns} for element in polygon]

        engine = self.db.bind
        if_exists_option = 'append' if increment else 'replace'
        polygon.to_postgis(table_name, engine, if_exists=if_exists_option)

    def upload_raster(
        self,
        raster_path: str,
        table_name: str,
        srid: int,
        increment: bool = True,
        new_columns: list = None
    ) -> None:
        table_name = table_name.replace("-", "_")
        # Drop the previous table if isnt to increment
        if not increment:
            drop_table_command = f"DROP TABLE IF EXISTS {table_name};"
            self.db.execute(text(drop_table_command))
            self.db.commit()

        database_url = getenv('DATABASE_URL')
        # Upload the raster - change the database
        raster2pgsql_command = f"""
            raster2pgsql -F -I -C -s {srid} -t 256x256 {raster_path} {table_name}  |
            psql {database_url}
        """
        subprocess.run(raster2pgsql_command, shell=True)

        if (not new_columns):
            return

        # Add the new columns to the new rows
        metadata = MetaData(bind=self.db.bind)
        raster_table = Table(table_name, metadata, autoload=True)
        raster_table_update = raster_table.update()

        first_column = next(iter(new_columns))
        raster_table_update.where(getattr(raster_table.c, first_column) == None)
        raster_table_update.values({column: value for column, value in new_columns.items()})

        self.db.execute(text(raster_table_update))
        self.db.commit()

    async def get_polygon_by_name(self, table_name) -> GeoJSON:

        polygon = geopandas.read_postgis(f'select * from {table_name}', geom_col='geometry', con=self.db.bind)
        return polygon.to_json()

    async def get_raster(self, table_name, x, y, z) -> Geometry | None:

        sql_query = f"""
            SELECT ST_AsGDALRaster(ST_Union(ST_ColorMap(rast, 1, 'bluered')), 'PNG') AS rast_data
            FROM {table_name}
            WHERE ST_Intersects(rast, ST_Transform(ST_TileEnvelope({z}, {x}, {y}), 4674));
        """
        result = await self.db.execute(text(sql_query))
        raster_datas = result.fetchone()

        if raster_datas:
            return raster_datas[0]
        else:
            return None

    async def get_geofile_by_name(self, table_name):

        query = select(Geodata.name, Geodata.geotype).filter_by(name=table_name).fetch(1)
        data = await self.db.exec(query)
        return data.first()

    async def get_raster_dataset(self, table_name) -> Dataset | None:

        sql_query = f"SELECT ST_AsGDALRaster(ST_Union(rast), 'GTiff') AS rast_data FROM {table_name};"
        result = await self.db.execute(text(sql_query))
        raster_datas = result.fetchone()
        if not raster_datas:
            return None

        with tempfile.NamedTemporaryFile(suffix=".tif", delete=False) as temp_file:
            temp_file.write(raster_datas[0])

        dataset = gdal.Open(temp_file.name)
        os.remove(temp_file.name)

        return dataset
