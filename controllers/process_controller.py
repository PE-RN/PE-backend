import os

from fastapi import status
from fastapi.exceptions import HTTPException

from schemas.geojson import GeoJSON
from scripts.create_raster_obj import read_raster_as_json
from scripts.geo_processing import clip_and_get_pixel_values


class ProcessController:

    def __init__(self):
        pass

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

    async def process_geo_process(self, geoJSON: GeoJSON):

        self._validate_features(geoJSON)

        tiff_name = os.getenv("TIFF_NAME_GEO_PROCESS")
        actual_path = os.getcwd()
        path_tiff = actual_path + '/scripts/data/' + tiff_name
        return await clip_and_get_pixel_values(geoJSON.features, path_tiff)

    async def process_raster(self, raster_name: str):

        actual_path = os.getcwd()
        path_tiff = actual_path + '/scripts/data/' + raster_name
        return await read_raster_as_json(path_tiff)
