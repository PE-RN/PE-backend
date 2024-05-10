import os
from contextlib import asynccontextmanager
from typing import Annotated
from uuid import UUID

import sentry_sdk
from dotenv import load_dotenv
from fastapi import Body, Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import EmailStr

from controllers.auth_controller import AuthController
from controllers.process_controller import ProcessController
from controllers.user_controller import UserController
from schemas.geojson import GeoJSON
from schemas.token import Token
from schemas.user import UserCreate
from sql_app import models
from sql_app.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):

    if os.getenv('ENVIRONMENT', 'local') == 'local':
        load_dotenv('.env')

    if os.getenv('ENVIRONMENT') != 'local':
        sentry_sdk.init(
            dsn="https://f758514d23ea1004b84fcacf3fd3e70e@o4507067706245120.ingest.us.sentry.io/4507067723939840",
            # Set traces_sample_rate to 1.0 to capture 100%
            # of transactions for performance monitoring.
            traces_sample_rate=1.0,
            environment=os.getenv("ENVIRONMENT"),
            # Set profiles_sample_rate to 1.0 to profile 100%
            # of sampled transactions.
            # We recommend adjusting this value in production.
            profiles_sample_rate=1.0,
        )

    await init_db()
    yield


app = FastAPI(lifespan=lifespan)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000"],  # Allows only requests from localhost:8000
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)


@app.post("/token")
async def login(
    password: Annotated[str, Body()],
    email: Annotated[EmailStr | None, Body()],
    controller: Annotated[AuthController, Depends(AuthController.inject_controller)]
):

    return await controller.get_acess_token_user(email=email, password=password)


@app.post('/refresh-token', response_model=Token)
async def refresh_token(
    token: Annotated[str, Body()],
    controller: Annotated[AuthController, Depends(AuthController.inject_controller)]
):

    return await controller.refresh_tokens(token=token)


@app.get("/confirm-email/{temporary_user_id}")
async def confirm_email(
    temporary_user_id: UUID,
    controller: Annotated[AuthController, Depends(AuthController.inject_controller)]
) -> None:

    return await controller.confirm_email(temporary_user_id=temporary_user_id)


@app.post("/users", response_model=models.TemporaryUser)
async def post_users(
    user: UserCreate, 
    controller: Annotated[UserController, Depends(UserController.inject_controller)]
):

    return await controller.create_temporary_user(user)


@app.post("/process/geo-processing")
async def post_process_geo_processing(
    geoJSON: GeoJSON,
    user: Annotated[models.User, Depends(AuthController.get_user_from_token)],
    controller: Annotated[ProcessController, Depends(ProcessController.inject_controller)]
):

    return await controller.process_geo_process(geoJSON)


@app.get("/process/raster/{raster_name}")
async def post_process_raster(
    raster_name: str,
    controller: Annotated[ProcessController, Depends(ProcessController.inject_controller)]
):
    return await controller.process_raster(raster_name)
