from fastapi import status, Response
from fastapi.responses import StreamingResponse
from io import BytesIO
from repositories.geo_repository import GeoRepository
from schemas.geojson import GeoJSON


class GeoFilesController:

    def __init__(self, repository: GeoRepository):
        self.repository = repository

    async def _validate_geofile(self, table_name: str, type: str) -> tuple[bool, dict]:

        error_response = None
        has_error = False

        geofile = await self.repository.validade_geofile(table_name)
        if geofile is None:
            has_error = True
            error_response = {"Bad Request": "Geofile doesn't exist"}
        elif not geofile.name or not geofile.geotype:
            has_error = True
            error_response = {"Bad Request": "Geofile name or type is missing"}
        elif not geofile.geotype == type:
            has_error = True
            error_response = {"Bad Request": "Incorrect type of geometry"}

        return has_error, error_response

    async def get_polygon(self, table_name: str, response: Response) -> GeoJSON:

        has_error, error_response = await self._validate_geofile(table_name, 'polygon')
        if has_error:
            response.status_code = status.HTTP_400_BAD_REQUEST
            return error_response

        try:
            return await self.repository.get_polygon(table_name)
        except Exception as error:
            response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
            return {"Internal Server Error": error}

    async def get_raster(self, table_name: str, response: Response, x, y, z):

        has_error, error_response = await self._validate_geofile(table_name, 'raster')
        if has_error:
            response.status_code = status.HTTP_400_BAD_REQUEST
            return error_response

        try:
            raster_file = await self.repository.get_raster(table_name, x, y, z)

            return StreamingResponse(
                raster_file,
                media_type="image/png",
                headers={"Content-Disposition": "attachment; filename=raster.png"}
            )
        except Exception as error:
            response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
            return {"Internal Server Error": error}
