from repositories.geo_repository import GeoRepository
from schemas.geojson import GeoJSON


class GeoFilesController:

    def __init__(self, repository: GeoRepository):
        self.repository = repository

    async def get_polygon(self, table_name: str) -> GeoJSON:
        return await self.repository.get_polygon(table_name=table_name)
