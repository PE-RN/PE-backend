from pydantic import EmailStr
from typing import Annotated
from datetime import datetime, timedelta, timezone
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, Response, Depends, Body, BackgroundTasks
from schemas.geojson import GeoJSON
from sqlalchemy.orm import Session
import sentry_sdk
import os
from contextlib import asynccontextmanager
from sql_app.database import init_db
from sql_app import models
from jose import JWTError, jwt
from sql_app.database import SessionLocal
import sql_app.models
from schemas.user import UserCreate
from schemas.token import Token
from services.email_service import EmailService
from controllers.user_controller import UserController
from repositories.user_repository import UserRepository
from controllers.process_controller import ProcessController
from controllers.auth_controller import AuthController
from repositories.auth_repository import AuthRepository
from  uuid import UUID

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


# Dependency
async def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        await db.close()

@asynccontextmanager
async def lifespan(app: FastAPI):
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
async def login(password: Annotated[str, Body()], email: Annotated[EmailStr | None, Body()], db: Annotated[Session, Depends(get_db)]):
    controller = AuthController(repository=AuthRepository(db=db))
    return await controller.get_acess_token_user(email=email,password=password)

@app.post('/refresh-token')
async def refresh_token(token: Annotated[str, Body()], db: Annotated[Session, Depends(get_db)]):
    controller = AuthController(repository=AuthRepository(db=db))
    return await controller.refresh_tokens(token=token)

@app.post("/confirm-email/{temporary_user_id}")
async def confirm_email(temporary_user_id: UUID, db: Annotated[Session, Depends(get_db)]):
    controller = AuthController(repository=AuthRepository(db=db))
    return await controller.confirm_email(temporary_user_id=temporary_user_id)


@app.post("/users", response_model=models.TemporaryUser)
async def post_users(user: UserCreate,background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    controller = UserController(repository=UserRepository(db=db),
                                email_service=EmailService(
                                    host="smtp-mail.outlook.com",
                                    port="587",
                                    email="platenergiasrn@isi-er.com.br",
                                    password="DevsISI00"),
                                    background_tasks=background_tasks
                                )
    
    return await controller.create_temporary_user(user)

@app.post("/process/geo-processing")
async def post_process_geo_processing(geoJSON: GeoJSON, response: Response):
    controller = ProcessController()
    return await controller.process_geo_process(geoJSON, response)

@app.get("/process/raster/{raster_name}")
async def post_process_raster(raster_name: str):
    controller = ProcessController()
    return await controller.process_raster(raster_name)