import os

from fastapi import Response, status

from schemas.geojson import GeoJSON
from scripts.create_raster_obj import read_raster_as_json
from scripts.geo_processing import clip_and_get_pixel_values


class ProcessController:

    def __init__(self):
        pass

    def inject_controller():
        return ProcessController()

    def _validate_features(self, geoJSON: GeoJSON) -> tuple[bool, dict]:
        error_response = None
        has_error = False
        for feature in geoJSON.features:
            if not (feature.geometry.type in {"Polygon", "MultiPolygon"}):
                has_error = True
                error_response = {"Bad Request": "Type of geometry not supported"}
            if (feature.geometry.type == 'Polygon' and len(feature.geometry.coordinates[0]) < 4):
                has_error = True
                error_response = {"Bad Request": "Incorrect number of coordinates"}
            if feature.geometry.type == 'Polygon' and feature.geometry.coordinates[0][-1] != feature.geometry.coordinates[0][0]:
                has_error = True
                error_response = {"Bad Request": "Incorrect coordinates in Polygon"}

        return has_error, error_response

    async def process_geo_process(self, geoJSON: GeoJSON, response: Response):

        has_error, error_response = self._validate_features(geoJSON)
        if has_error:
            response.status_code = status.HTTP_400_BAD_REQUEST
            return error_response

        tiff_name = "VELOCIDADE_150M.tif"
        actual_path = os.getcwd()
        path_tiff = actual_path + '/scripts/data/' + tiff_name
        return await clip_and_get_pixel_values(geoJSON.features, path_tiff)

    async def process_raster(self, raster_name: str):

        actual_path = os.getcwd()
        path_tiff = actual_path + '/scripts/data/' + raster_name
        return await read_raster_as_json(path_tiff)
