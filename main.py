from fastapi import FastAPI, Response, status
from models.geojson import GeoJSONModel
from scripts.hydrogen_costs import hydrogen_costs
from scripts.geo_processing import clip_and_get_pixel_values
import sentry_sdk
import os

if not os.getenv('SENTRY_ENVIRONMENT', 'local') == 'local':

    sentry_sdk.init(
        dsn="https://f758514d23ea1004b84fcacf3fd3e70e@o4507067706245120.ingest.us.sentry.io/4507067723939840",
        # Set traces_sample_rate to 1.0 to capture 100%
        # of transactions for performance monitoring.
        traces_sample_rate=1.0,
        environment=os.getenv("SENTRY_ENVIRONMENT"),
        # Set profiles_sample_rate to 1.0 to profile 100%
        # of sampled transactions.
        # We recommend adjusting this value in production.
        profiles_sample_rate=1.0,
    )

app = FastAPI()


@app.post("/process/geo-processing")
async def post_process_geo_processing(geoJSON: GeoJSONModel, response: Response):
    tiff_name = "VELOCIDADE_150M.tif"
    actual_path = os.getcwd()
    path_tiff = actual_path + '/scripts/data/' + tiff_name
    for feature in geoJSON.features:
        if not (feature.geometry.type in {"Polygon", "MultiPolygon"}):
            response.status_code = status.HTTP_400_BAD_REQUEST
            return {"Bad Request": "Type of geometry not supported"}
        if len(feature.geometry.coordinates[0]) < 4:
            response.status_code = status.HTTP_400_BAD_REQUEST
            return {"Bad Request": "Incorrect number of coordinates"}
        if feature.geometry.type == 'Polygon' and feature.geometry.coordinates[0][-1] != feature.geometry.coordinates[0][0]:
            response.status_code = status.HTTP_400_BAD_REQUEST
            return {"Bad Request": "Incorrect coordinates in Polygon"}

    return await clip_and_get_pixel_values(geoJSON.features, path_tiff)


@app.get("/sentry-debug")
async def trigger_error():
    division_by_zero = 1/0
    return division_by_zero


@app.post("/process/hydrogen-costs")
async def post_hydrogen_process_costs(geojson: GeoJSONModel):
    return await hydrogen_costs(geoJSON=geojson)
