from fastapi import FastAPI
from models.geojson import GeoJSONModel
from scripts.hydrogen_costs import hydrogen_costs
import sentry_sdk


sentry_sdk.init(
    dsn="https://f758514d23ea1004b84fcacf3fd3e70e@o4507067706245120.ingest.us.sentry.io/4507067723939840",
    # Set traces_sample_rate to 1.0 to capture 100%
    # of transactions for performance monitoring.
    traces_sample_rate=1.0,
    # Set profiles_sample_rate to 1.0 to profile 100%
    # of sampled transactions.
    # We recommend adjusting this value in production.
    profiles_sample_rate=1.0,
)

app = FastAPI()

@app.get("/sentry-debug")
async def trigger_error():
    division_by_zero = 1/0

@app.post("/process/hydrogen-costs")
async def post_hydrogen_process_costs(geojson: GeoJSONModel):
    
    return await hydrogen_costs(geoJSON=geojson)
