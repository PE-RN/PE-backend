from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, Response, Depends
from schemas.geojson import GeoJSON
from scripts.hydrogen_costs import hydrogen_costs
from sqlalchemy.orm import Session
import sentry_sdk
import os
from sql_app import models
from sql_app.database import engine, SessionLocal
from schemas.user import UserCreate, User
from controllers.user_controller import UserController
from repositories.user_repository import UserRepository
from controllers.process_controller import ProcessController

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

models.Base.metadata.create_all(bind=engine)


# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)


@app.post("/users", response_model=User)
async def post_users(user: UserCreate, db: Session = Depends(get_db)):
    controller = UserController(repository=UserRepository(db=db))
    return controller.create_user(user)


@app.post("/process/geo-processing")
async def post_process_geo_processing(geoJSON: GeoJSON, response: Response):
    controller = ProcessController()
    return await controller.process_geo_process(geoJSON, response)


@app.get("/process/raster/{raster_name}")
async def post_process_raster(raster_name: str):
    controller = ProcessController()
    return await controller.process_raster(raster_name)


@app.get("/sentry-debug")
async def trigger_error():
    division_by_zero = 1/0
    return division_by_zero


@app.post("/process/hydrogen-costs")
async def post_hydrogen_process_costs(geojson: GeoJSON):
    return await hydrogen_costs(geoJSON=geojson)
