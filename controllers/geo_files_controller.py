from fastapi import status, Response
from repositories.geo_repository import GeoRepository
from schemas.geojson import GeoJSON


class GeoFilesController:

    def __init__(self, repository: GeoRepository):
        self.repository = repository

    async def _validate_polygon(self, table_name: str) -> tuple[bool, dict]:

        error_response = None
        has_error = False

        geofile = await self.repository.validade_geofile(table_name)
        if geofile is None:
            has_error = True
            error_response = {"Bad Request": "Geofile doesn't exist"}
        elif not geofile.name or not geofile.geotype:
            has_error = True
            error_response = {"Bad Request": "Geofile name or type is missing"}
        elif not geofile.geotype == 'polygon':
            has_error = True
            error_response = {"Bad Request": "Type of geometry not supported"}

        return has_error, error_response

    async def get_polygon(self, table_name: str, response: Response) -> GeoJSON:

        has_error, error_response = await self._validate_polygon(table_name)
        if has_error:
            response.status_code = status.HTTP_400_BAD_REQUEST
            return error_response

        try:
            return await self.repository.get_polygon(table_name=table_name)
        except Exception as error:
            response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
            return {"Internal Server Error": error}
