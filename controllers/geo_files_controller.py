from typing import Annotated

from fastapi import Depends, status
from fastapi.responses import StreamingResponse
from fastapi.exceptions import HTTPException
from sqlmodel.ext.asyncio.session import AsyncSession

from repositories.geo_repository import GeoRepository
from schemas.geojson import GeoJSON
from sentry_sdk import capture_exception
from sql_app.database import get_db


class GeoFilesController:

    def __init__(self, repository: GeoRepository):
        self.repository = repository

    @staticmethod
    async def inject_controller(db: Annotated[AsyncSession, Depends(get_db)]):

        return GeoFilesController(
            repository=GeoRepository(db=db)
        )

    def _validate_geofile(self, table_name: str, type: str) -> tuple[bool, dict]:

        geofile = self.repository.validade_geofile(table_name)
        if geofile is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Geofile doesn't exist")
        elif not geofile['name'] or not geofile['geotype']:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Geofile name or type is missing")
        elif not geofile['geotype'] == type:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Incorrect type of geometry")

    async def get_polygon(self, table_name: str) -> GeoJSON:

        self._validate_geofile(table_name, 'polygon')
        try:
            return await self.repository.get_polygon(table_name)
        except Exception as error:
            capture_exception(error)
            return HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=error)

    async def get_raster(self, table_name: str, x: int, y: int, z: int):

        await self._validate_geofile(table_name, 'raster')
        try:
            raster_file = await self.repository.get_raster(table_name, x, y, z)

            return StreamingResponse(
                raster_file,
                media_type="image/png",
                headers={"Content-Disposition": "attachment; filename=raster.png"}
            )
        except Exception as error:
            capture_exception(error)
            return HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=error)
