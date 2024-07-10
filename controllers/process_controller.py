from typing import Annotated

from fastapi import Depends, status
from fastapi.exceptions import HTTPException
from sqlmodel.ext.asyncio.session import AsyncSession

from repositories.geo_repository import GeoRepository
from schemas.geojson import GeoJSON
from scripts.create_raster_obj import read_raster_as_json
from scripts.geo_processing import clip_and_get_pixel_values
from scripts.dash_data import mean_stats
from sql_app.database import get_db


class ProcessController:

    def __init__(self, repository: GeoRepository):
        self.repository = repository

    @staticmethod
    async def inject_controller(db: Annotated[AsyncSession, Depends(get_db)]):

        return ProcessController(
            repository=GeoRepository(db=db)
        )

    def _validate_features(self, geoJSON: GeoJSON) -> None:

        for feature in geoJSON.features:
            if not (feature.geometry.type in {"Polygon", "MultiPolygon"}):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Type of geometry not supported")
            if (feature.geometry.type == 'Polygon' and len(feature.geometry.coordinates[0]) < 4):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Incorrect number of coordinates")
            if feature.geometry.type == 'Polygon' and feature.geometry.coordinates[0][-1] != feature.geometry.coordinates[0][0]:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Incorrect coordinates in Polygon")

    async def process_geo_process(self, geoJSON: GeoJSON, raster_name: str):

        self._validate_features(geoJSON)

        dataset = await self.repository.get_raster_dataset(raster_name)
        if not dataset:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail='Problemas no processamento!')
        return await clip_and_get_pixel_values(geoJSON.features, dataset)

    async def process_raster(self, raster_name: str):

        dataset = await self.repository.get_raster_dataset(raster_name)
        if not dataset:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail='Problemas no processamento!')
        return await read_raster_as_json(dataset)

    async def dash_data(self, geoJSON: GeoJSON, energy_type: str):

        self._validate_features(geoJSON)

        json_data = await self.repository.get_geo_json_data_by_name(energy_type)
        if not json_data:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Problemas no processamento!")

        return await mean_stats(json_data.data, geoJSON.model_dump())

    async def create_geo_json_data(self, geoJSON: GeoJSON, name: str):

        self._validate_features(geoJSON)

        return await self.repository.create_geo_json_data(data=geoJSON, name=name)
