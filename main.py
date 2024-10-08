import os
from contextlib import asynccontextmanager
from typing import Annotated
from uuid import UUID

import sentry_sdk
from dotenv import load_dotenv, find_dotenv
from fastapi import Body, Depends, FastAPI, status, Response
from fastapi.exceptions import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import EmailStr

from controllers.auth_controller import AuthController
from controllers.feedback_controller import FeedbackController
from controllers.geo_files_controller import GeoFilesController
from controllers.process_controller import ProcessController
from controllers.user_controller import UserController
from controllers.media_controller import MediaController
from schemas.feature import Feature
from schemas.feedback import FeedbackCreate
from schemas.token import Token
from schemas.user import UserCreate
from schemas.media import CreatePdf, CreateVideo
from sql_app import models
from sql_app.database import init_db
from enums.ocupation_enum import OcupationEnum


@asynccontextmanager
async def lifespan(app: FastAPI):

    if os.getenv('ENVIRONMENT', 'local') not in {'production', 'development'}:
        load_dotenv(find_dotenv())
    if os.getenv('ENVIRONMENT') in {'production', 'development'}:
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
    allow_origins=["http://localhost:8000", "https://plataforma-energias-rn-production.up.railway.app"],
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)


@app.post("/token")
async def login(
    password: Annotated[str, Body()],
    email: Annotated[EmailStr | None, Body()],
    controller: Annotated[AuthController, Depends(AuthController.inject_controller)]
) -> Token:

    return await controller.get_token_user(email=email, password=password)


@app.post('/refresh-token', response_model=Token)
async def refresh_token(
    refresh_token: Annotated[str, Body(embed=True)],
    controller: Annotated[AuthController, Depends(AuthController.inject_controller)]
):

    return await controller.refresh_tokens(token=refresh_token)


@app.get("/confirm-email/{temporary_user_id}")
async def confirm_email(
    temporary_user_id: UUID,
    controller: Annotated[AuthController, Depends(AuthController.inject_controller)]
) -> None:

    return await controller.confirm_email(temporary_user_id=temporary_user_id)


@app.post("/users",
          response_model=models.TemporaryUser,
          response_model_exclude={"password", "updated_at", "deleted_at"},
          status_code=status.HTTP_201_CREATED)
async def post_users(
    user: UserCreate,
    controller: Annotated[UserController, Depends(UserController.inject_controller)]
):

    return await controller.create_temporary_user(user)


@app.put("/users",
          response_model=models.User,
          response_model_exclude={"password", "created_at", "updated_at", "deleted_at"},
          status_code=status.HTTP_200_OK)
async def update_users(
    user_update: dict,
    user: Annotated[models.User, Depends(AuthController.get_user_from_token)],
    controller: Annotated[UserController, Depends(UserController.inject_controller)],
    has_permission: Annotated[bool, Depends(AuthController.get_permission_dependency("update_user"))]
):

    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Não possui permissão.")

    return await controller.update_user(user, user_update)


@app.get("/recovery-password/{user_email}", status_code=status.HTTP_200_OK)
async def get_recovery_password(
    user_email: str,
    controller: Annotated[AuthController, Depends(AuthController.inject_controller)]
):
    return await controller.recovery_password(user_email)


@app.post("/change-password", status_code=status.HTTP_200_OK)
async def post_change_password(
    user: Annotated[models.User | models.AnonymousUser, Depends(AuthController.get_user_from_token)],
    password: Annotated[str, Body()],
    new_password: Annotated[str, Body()],
    controller: Annotated[AuthController, Depends(AuthController.inject_controller)]
):
    return await controller.change_password(user, password, new_password)


@app.post("/process/geo-processing/{raster_name}")
async def post_process_geo_processing(
    feature: Feature,
    raster_name: str,
    user: Annotated[models.User | models.AnonymousUser, Depends(AuthController.get_user_from_token)],
    controller: Annotated[ProcessController, Depends(ProcessController.inject_controller)],
    has_permission: Annotated[bool, Depends(AuthController.get_permission_dependency("view_geo_processing"))]
):

    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Não possui permissão.")

    return await controller.process_geo_process(feature, raster_name, user.id.hex)


@app.get("/process/raster/{raster_name}")
async def post_process_raster(
    raster_name: str,
    controller: Annotated[ProcessController, Depends(ProcessController.inject_controller)],
    user: Annotated[models.User | models.AnonymousUser, Depends(AuthController.get_user_from_token)],
    has_permission: Annotated[bool, Depends(AuthController.get_permission_dependency("view_raster"))]
):

    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Não possui permissão.")

    return await controller.process_raster(raster_name, user.id.hex)


@app.post("/process/dash-data/{energy_type}")
async def get_dash_data(
    feature: Feature,
    energy_type: str,
    user: Annotated[models.User, Depends(AuthController.get_user_from_token)],
    controller: Annotated[ProcessController, Depends(ProcessController.inject_controller)],
    has_permission: Annotated[bool, Depends(AuthController.get_permission_dependency("view_dash_data"))]
):

    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Não possui permissão.")

    return await controller.dash_data(feature, energy_type)


@app.get("/sentry-debug")
async def trigger_error():
    division_by_zero = 1 / 0
    return division_by_zero


@app.get("/geofiles/polygon/{table_name}")
async def get_geofiles_polygon(
    table_name: str,
    response: Response,
    controller: Annotated[GeoFilesController, Depends(GeoFilesController.inject_controller)],
    has_permission: Annotated[bool, Depends(AuthController.get_permission_dependency("view_polygon"))]
):

    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Não possui permissão.")
    return await controller.get_polygon(table_name=table_name, response=response)


@app.get("/geofiles/raster/{z}/{x}/{y}/{table_name}")
async def get_geofiles_raster(
    table_name: str,
    x,
    y,
    z,
    controller: Annotated[GeoFilesController, Depends(GeoFilesController.inject_controller)],
    has_permission: Annotated[bool, Depends(AuthController.get_permission_dependency("view_raster"))]
):

    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Não possui permissão.")

    return await controller.get_raster(table_name=table_name, x=x, y=y, z=z)


@app.post("/media/pdf",
          response_model=models.PdfFile,
          response_model_exclude={"updated_at", "deleted_at"})
async def post_pdf(
    pdf: CreatePdf,
    user: Annotated[models.User | models.AnonymousUser, Depends(AuthController.get_user_from_token)],
    controller: Annotated[MediaController, Depends(MediaController.inject_controller)],
    has_permission: Annotated[bool, Depends(AuthController.get_permission_dependency("upload_pdf"))]
):

    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Não possui permissão.")

    return await controller.create_pdf(pdf)


@app.get("/media/pdf/{pdf_id}",
         response_model=models.PdfFile,
         response_model_exclude={"updated_at", "deleted_at"})
async def get_pdf(
    pdf_id: str,
    user: Annotated[models.User | models.AnonymousUser, Depends(AuthController.get_user_from_token)],
    controller: Annotated[MediaController, Depends(MediaController.inject_controller)],
    has_permission: Annotated[bool, Depends(AuthController.get_permission_dependency("view_pdf"))]
):

    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Não possui permissão.")

    return await controller.get_pdf(pdf_id)


@app.get("/media/pdf", response_model=list[models.PdfFile])
async def list_pdf(
    user: Annotated[models.User | models.AnonymousUser, Depends(AuthController.get_user_from_token)],
    controller: Annotated[MediaController, Depends(MediaController.inject_controller)],
    has_permission: Annotated[bool, Depends(AuthController.get_permission_dependency("list_pdf"))]
):

    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Não possui permissão.")

    return await controller.list_pdf()


@app.post("/media/video",
          response_model=models.Video,
          response_model_exclude={"updated_at", "deleted_at"})
async def post_video(
    video: CreateVideo,
    user: Annotated[models.User | models.AnonymousUser, Depends(AuthController.get_user_from_token)],
    controller: Annotated[MediaController, Depends(MediaController.inject_controller)],
    has_permission: Annotated[bool, Depends(AuthController.get_permission_dependency("upload_video"))]
):

    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Não possui permissão.")

    return await controller.create_video(video)


@app.get("/media/video/{video_id}",
         response_model=models.Video,
         response_model_exclude={"updated_at", "deleted_at"})
async def get_video(
    video_id: str,
    user: Annotated[models.User | models.AnonymousUser, Depends(AuthController.get_user_from_token)],
    controller: Annotated[MediaController, Depends(MediaController.inject_controller)],
    has_permission: Annotated[bool, Depends(AuthController.get_permission_dependency("view_video"))]
):

    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Não possui permissão.")

    return await controller.get_video(video_id)


@app.get("/media/video",
         response_model=list[models.Video])
async def list_video(
    user: Annotated[models.User | models.AnonymousUser, Depends(AuthController.get_user_from_token)],
    controller: Annotated[MediaController, Depends(MediaController.inject_controller)],
    has_permission: Annotated[bool, Depends(AuthController.get_permission_dependency("list_video"))]
):

    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Não possui permissão.")

    return await controller.list_video()


@app.get("/geofiles/download/{table_name}", status_code=status.HTTP_200_OK)
async def get_file_download(
    table_name: str,
    controller: Annotated[GeoFilesController, Depends(GeoFilesController.inject_controller)],
    has_permission: Annotated[bool, Depends(AuthController.get_permission_dependency("get_geofile"))]
):

    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Não possui permissão.")

    return await controller.get_geofile_download(table_name)


@app.post("/anonymous", status_code=status.HTTP_201_CREATED)
async def post_anonymous(
    ocupation: Annotated[OcupationEnum, Body(embed=True)],
    controller: Annotated[AuthController, Depends(AuthController.inject_controller)]
):
    return await controller.create_anonymous_user(ocupation=ocupation)


@app.post("/contact",
          response_model=models.Feedback,
          response_model_exclude={"updated_at", "deleted_at"})
async def post_contact(
    contact: FeedbackCreate,
    user: Annotated[models.User | models.AnonymousUser, Depends(AuthController.get_user_from_token)],
    controller: Annotated[FeedbackController, Depends(FeedbackController.inject_controller)],
    has_permission: Annotated[bool, Depends(AuthController.get_permission_dependency("create_contact"))]
):

    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Não possui permissão.")

    return await controller.create_feedback(contact)
