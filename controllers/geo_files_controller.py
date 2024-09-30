from typing import Annotated

from fastapi import Depends, status, UploadFile
from fastapi.responses import StreamingResponse
from fastapi.exceptions import HTTPException
from io import BytesIO
from sqlmodel.ext.asyncio.session import AsyncSession

from repositories.geo_repository import GeoRepository
from schemas.geojson import GeoJSON
from sentry_sdk import capture_exception
from sql_app.database import get_db

import os


class GeoFilesController:

    def __init__(self, repository: GeoRepository):
        self.repository = repository

    @staticmethod
    async def inject_controller(db: Annotated[AsyncSession, Depends(get_db)]):

        return GeoFilesController(
            repository=GeoRepository(db=db)
        )

    async def _validate_geofile(self, table_name: str, type: str) -> None:

        geofile = await self.repository.get_geofile_by_name(table_name)
        if geofile is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Geofile não existe!")
        elif not geofile[0] or not geofile[1]:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Geofile nome ou tipo faltando!")
        elif not geofile[1] == type:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tipo incorreto de geometria!")

    async def get_polygon(self, table_name: str) -> GeoJSON:

        await self._validate_geofile(table_name, 'polygon')
        try:
            return await self.repository.get_polygon_by_name(table_name)
        except Exception as error:
            capture_exception(error)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=error)

    async def get_raster(self, table_name: str, x: int, y: int, z: int):

        raster_file = await self.repository.get_raster(table_name, x, y, z)
        if not raster_file:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail='Raster file não processado!')

        image = BytesIO(raster_file)
        return StreamingResponse(
            image,
            media_type="image/png",
            headers={"Content-Disposition": "attachment; filename=raster.png"}
        )

    async def get_geofile_download(self, table_name: str):

        try:
            return await self.repository.get_geofile_download(table_name)

        except Exception as error:
            capture_exception(error)
            return HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=error)

    async def upload_raster(
        self,
        fd: int,
        file: UploadFile,
        raster_path: str,
        table_name: str,
        srid: int
    ) -> None:

        try:
            with os.fdopen(fd, "wb") as tmp:
                tmp.write(await file.read())

            return await self.repository.upload_raster(raster_path, table_name, srid, False)

        except Exception as error:
            capture_exception(error)
            return HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=error)

        finally:
            if os.path.exists(raster_path):
                os.unlink(raster_path)
