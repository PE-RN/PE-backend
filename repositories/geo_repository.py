import asyncio
import os
import tempfile
from asyncio.subprocess import DEVNULL, PIPE
import re
from typing import TYPE_CHECKING

from os import getenv
from sqlalchemy import MetaData, Table, text
from sqlmodel.ext.asyncio.session import AsyncSession

from schemas.geojson import GeoJSON
from schemas.geometry import Geometry
from sql_app.models import Geodata, GeoJsonData
from sqlmodel import select

if TYPE_CHECKING:
    import geopandas
    from osgeo.gdal import Dataset


class GeoRepository:

    TABLE_NAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

    def __init__(self, db: AsyncSession):
        self.db = db

    @classmethod
    def normalize_table_name(cls, table_name: str) -> str:

        normalized_table_name = table_name.strip().replace("-", "_").replace(" ", "_").lower()

        if not normalized_table_name:
            raise ValueError("Nome da tabela inválido.")

        if not cls.TABLE_NAME_PATTERN.fullmatch(normalized_table_name):
            raise ValueError("Nome da tabela inválido. Use apenas letras, números e underscore.")

        return normalized_table_name

    def upload_polygon(self, polygon: "geopandas.GeoDataFrame", table_name: str, increment: bool = True, new_columns: list = None):

        import geopandas

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
    ) -> dict:
        table_name = self.normalize_table_name(table_name)
        # Drop the previous table if isnt to increment
        if not increment:
            drop_table_command = f"DROP TABLE IF EXISTS {table_name};"
            await self.db.exec(text(drop_table_command))
            await self.db.commit()

        database_url = getenv('SYNC_DATABASE_URL')

        if not database_url:
            raise ValueError("SYNC_DATABASE_URL não está definida.")

        with tempfile.NamedTemporaryFile(suffix=".sql", delete=False) as sql_file:
            sql_file_path = sql_file.name
        with tempfile.NamedTemporaryFile(suffix=".log", delete=False) as stdout_file:
            stdout_file_path = stdout_file.name
        with tempfile.NamedTemporaryFile(suffix=".log", delete=False) as stderr_file:
            stderr_file_path = stderr_file.name

        try:
            raster2pgsql_stderr = b""
            with open(sql_file_path, "wb") as sql_output:
                raster2pgsql_process = await asyncio.create_subprocess_exec(
                    "raster2pgsql",
                    "-F",
                    "-I",
                    "-C",
                    "-s",
                    str(srid),
                    "-t",
                    "256x256",
                    raster_path,
                    table_name,
                    stdout=sql_output,
                    stderr=PIPE,
                )
                _, raster2pgsql_stderr = await raster2pgsql_process.communicate()

            if raster2pgsql_process.returncode != 0:
                raise RuntimeError(raster2pgsql_stderr.decode().strip() or "Falha ao gerar o SQL do raster.")

            with open(stdout_file_path, "wb") as stdout_output, open(stderr_file_path, "wb") as stderr_output:
                psql_process = await asyncio.create_subprocess_exec(
                    "psql",
                    "-q",
                    "-d",
                    database_url,
                    "-f",
                    sql_file_path,
                    stdout=stdout_output,
                    stderr=stderr_output,
                    stdin=DEVNULL,
                )
                await psql_process.wait()

            with open(stdout_file_path, "r", encoding="utf-8", errors="ignore") as stdout_input:
                psql_stdout = stdout_input.read().strip()
            with open(stderr_file_path, "r", encoding="utf-8", errors="ignore") as stderr_input:
                psql_stderr = stderr_input.read().strip()

            if psql_process.returncode != 0:
                raise RuntimeError(psql_stderr or psql_stdout or "Falha ao importar o raster.")

            return {
                "table_name": table_name,
                "detail": "Raster importado com sucesso.",
                "output": psql_stdout,
            }
        finally:
            if os.path.exists(sql_file_path):
                os.unlink(sql_file_path)
            if os.path.exists(stdout_file_path):
                os.unlink(stdout_file_path)
            if os.path.exists(stderr_file_path):
                os.unlink(stderr_file_path)

    async def get_polygon_by_name(self, table_name) -> GeoJSON:

        import geopandas

        polygon = geopandas.read_postgis(f'select * from {table_name}', geom_col='geometry', con=self.db.bind)
        return polygon.to_json()

    async def get_raster(self, table_name, x, y, z) -> Geometry | None:

        sql_query = "set postgis.gdal_enabled_drivers = 'ENABLE_ALL';"
        await self.db.execute(text(sql_query))

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

    async def get_raster_dataset(self, table_name) -> "Dataset | None":

        from osgeo import gdal

        sql_query = "set postgis.gdal_enabled_drivers = 'ENABLE_ALL';"
        await self.db.execute(text(sql_query))

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

    async def get_geofile_download(self, table_name) -> str:

        query = select(Geodata.url_acess).filter_by(name=table_name).fetch(1)
        data = await self.db.exec(query)
        return data.first()

    async def get_geo_json_data_by_name(self, name) -> GeoJsonData | None:

        query = select(GeoJsonData).filter_by(name=name).fetch(1)
        data = await self.db.exec(query)
        return data.first()

    async def create_geo_json_data(self, data, name):

        geo_json_data = GeoJsonData(data=data, name=name)
        self.db.add(geo_json_data)
        await self.db.commit()
        await self.db.refresh(geo_json_data)
        return geo_json_data
