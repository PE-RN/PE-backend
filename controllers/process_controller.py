import os

from fastapi import status
from fastapi.exceptions import HTTPException

from repositories.geo_repository import GeoRepository
from schemas.geojson import GeoJSON
from scripts.create_raster_obj import read_raster_as_json
from scripts.geo_processing import clip_and_get_pixel_values


class ProcessController:

    def __init__(self, repository: GeoRepository):
        self.repository = repository

    def inject_controller():
        return ProcessController()

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

        actual_path = os.getcwd()
        path_tiff = actual_path + '/scripts/data/' + raster_name
        return await clip_and_get_pixel_values(geoJSON.features, path_tiff)

    async def process_raster(self, raster_name: str):

        dataset = await self.repository.get_raster_dataset(raster_name)
        return await read_raster_as_json(dataset)
