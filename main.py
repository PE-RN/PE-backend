import logging
import os
import shutil
import tempfile
import base64
from contextlib import asynccontextmanager
from typing import Annotated, Any, List
from uuid import UUID

import sentry_sdk
from dotenv import load_dotenv, find_dotenv
from fastapi import Body, Depends, BackgroundTasks, FastAPI, status, Response, UploadFile, HTTPException, Form, Body, File, Query, Request, Path as PathParam
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr
from typing import Union
from pathlib import Path
from typing import Optional, Annotated
import json
from datetime import datetime, time, date
import pandas as pd
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from controllers.auth_controller import AuthController
from controllers.admin_analytics_controller import AdminAnalyticsController, AdminAnalyticsValidationError
from controllers.feedback_controller import FeedbackController
from controllers.geo_files_controller import GeoFilesController
from controllers.process_controller import ProcessController
from controllers.user_controller import UserController
from controllers.media_controller import MediaController
from controllers.layers_controller import LayersController
from controllers.platform_wind import PlatformService
from schemas.adminStatusResponse import AdminStatusResponse
from schemas.admin_analytics import (
    AdminAnalyticsAdminOperationsQuery,
    AdminAnalyticsExportRequest,
    AdminAnalyticsFileUsageQuery,
    AdminAnalyticsFilterOptionsQuery,
    AdminAnalyticsMapUsageQuery,
    AdminAnalyticsOverviewQuery,
    AdminAnalyticsSystemHealthQuery,
    AdminAnalyticsUserActivityQuery,
)
from schemas.layers import LayerGroupCreate, LayerCreate
from schemas.feature import Feature
from schemas.featureCollection import FeatureCollection
from schemas.feedback import FeedbackCreate
from schemas.platform_wind import CreateDataStation
from schemas.token import Token
from schemas.user import UserCreate, UserUpdate
from schemas.media import MediaCreate, MediaUpdate
from services.admin_analytics_service import AdminAnalyticsTracker
from sql_app import models
from sql_app.database import init_db
from enums.ocupation_enum import OcupationEnum
from enums.platform_enum import DataStationType, WindRoseMode


BACKEND_ROOT = Path(__file__).resolve().parent
PUBLIC_ASSETS_DIR = BACKEND_ROOT / "assets" / "public"


def resolve_storage_path(path_value: str | None) -> Path | None:
    if not path_value:
        return None

    storage_path = Path(path_value)
    if storage_path.is_absolute():
        return storage_path

    return (BACKEND_ROOT / storage_path).resolve()


def _bind_layer_event_context(request: Request, layer: models.Layer) -> None:
    request.state.layer_event_context = {
        "layer_id": str(layer.id),
        "layer_name": layer.name,
        "group_id": str(layer.layer_group_id) if layer.layer_group_id else None,
    }

    saved_path = resolve_storage_path(layer.path)
    if saved_path is None or not saved_path.exists():
        return

    try:
        with saved_path.open("r", encoding="utf-8") as handle:
            geojson = json.load(handle)
        features = geojson.get("features", [])
        request.state.layer_upload_details = {
            "feature_count": len(features),
            "geometry_types": list(
                {
                    geometry["type"]
                    for feature in features
                    if (geometry := feature.get("geometry")) and geometry.get("type")
                }
            ),
        }
    except Exception:
        pass


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

app = FastAPI(lifespan=lifespan, dependencies=[Depends(AdminAnalyticsTracker.inject_tracker)])

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.middleware("http")
async def admin_analytics_middleware(request: Request, call_next):
    tracker = await AdminAnalyticsTracker.inject_tracker(request)
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    detail = None

    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    except Exception as exc:
        detail = str(exc)
        raise
    finally:
        if tracker.should_track_request():
            event_status = "error" if status_code >= 400 else "success"
            try:
                await tracker.record_system_health(
                    status_code=status_code,
                    status=event_status,
                    detail=detail,
                )
                business_event = tracker.build_business_event(
                    status_code=status_code,
                    status=event_status,
                    detail=detail,
                )
                if business_event is not None:
                    await tracker.record(**business_event)
            except Exception as analytics_exc:
                sentry_sdk.capture_exception(analytics_exc)


@app.middleware("http")
async def no_cache_middleware(request: Request, call_next):
    try:
        response = await call_next(request)
    except Exception:
        logging.exception("Unhandled exception reached no_cache_middleware")
        response = JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Erro interno do servidor."},
        )
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


@app.exception_handler(AdminAnalyticsValidationError)
async def admin_analytics_validation_exception_handler(
    request: Request,
    exc: AdminAnalyticsValidationError,
):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": exc.detail, "errors": exc.errors},
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logging.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Erro interno do servidor."},
    )

PUBLIC_ASSETS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/assets/public", StaticFiles(directory=str(PUBLIC_ASSETS_DIR)), name="public")


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "http://127.0.0.1:8000", "http://localhost:5173", "http://127.0.0.1:5173", "https://back.plataformadeenergiasrn.com.br", "https://plataformadeenergiasrn.com.br"],
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)


GeoJSONInput = Union[Feature, FeatureCollection]


class LayerUploadPreviewPayload(BaseModel):
    file_name: str
    feature_count: int
    geometry_types: list[str] = []
    geojson: dict[str, Any] | None = None


async def _save_raster_upload(
    raster_name: str,
    file: UploadFile,
    controller: GeoFilesController,
):
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Arquivo inválido.")

    extension = os.path.splitext(file.filename)[1].lower()

    if extension not in ('.tif', '.tiff'):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Extensão invalida.")

    fd, file_path = tempfile.mkstemp(prefix='raster_', suffix=extension)
    return await controller.upload_raster(fd, file, file_path, raster_name, 4674)


def _cookie_kwargs() -> dict:
    """Return cookie security flags appropriate for the current environment.
    In production/development (HTTPS) use Secure+Strict.
    In local dev (HTTP) use non-Secure+Lax so browsers accept cookies over plain HTTP.
    """
    if os.getenv("ENVIRONMENT", "local") in ("production", "development"):
        return {"httponly": True, "secure": True, "samesite": "strict"}
    return {"httponly": True, "secure": False, "samesite": "lax"}


@app.post("/token")
async def login(
    response: Response,
    password: Annotated[str, Body()],
    email: Annotated[EmailStr | None, Body()],
    controller: Annotated[AuthController, Depends(AuthController.inject_controller)]
) -> Token:

    token = await controller.get_token_user(email=email, password=password)
    if token == 'resend_email':
        return JSONResponse(
            content={"detail": 'Por favor clique no link do email de confirmação para realizar o login'},
            status_code=status.HTTP_401_UNAUTHORIZED
        )

    access_max_age = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 60)) * 60
    refresh_max_age = int(os.getenv("REFRESH_TOKEN_EXPIRE_MINUTES", 1440)) * 60
    ck = _cookie_kwargs()
    response.set_cookie("access_token", token.access_token, max_age=access_max_age, **ck)
    response.set_cookie("refresh_token", token.refresh_token, max_age=refresh_max_age, **ck)

    return token

@app.get("/check-token", response_model=AdminStatusResponse)
async def check_token(
    user: Annotated[models.User, Depends(AuthController.get_user_from_token)],
    controller: Annotated[AuthController, Depends(AuthController.inject_controller)],
    group_name: str = "admin"
):
    is_admin_status = await controller.user_is_admin(user=user, group_name=group_name)
    return {"is_admin": is_admin_status}


@app.post('/refresh-token', response_model=Token)
async def refresh_token(
    response: Response,
    request: Request,
    refresh_token: Annotated[str | None, Body(embed=True)] = None,
    controller: Annotated[AuthController, Depends(AuthController.inject_controller)] = None
):
    # Accept refresh token from body or from httpOnly cookie
    token_value = refresh_token or request.cookies.get("refresh_token")
    if not token_value:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido!")

    new_tokens = await controller.refresh_tokens(token=token_value)

    access_max_age = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 60)) * 60
    refresh_max_age = int(os.getenv("REFRESH_TOKEN_EXPIRE_MINUTES", 1440)) * 60
    ck = _cookie_kwargs()
    response.set_cookie("access_token", new_tokens.access_token, max_age=access_max_age, **ck)
    response.set_cookie("refresh_token", new_tokens.refresh_token, max_age=refresh_max_age, **ck)

    return new_tokens


@app.post("/logout", status_code=status.HTTP_200_OK)
async def logout(response: Response):
    ck = _cookie_kwargs()
    response.delete_cookie("access_token", samesite=ck["samesite"])
    response.delete_cookie("refresh_token", samesite=ck["samesite"])
    return {"detail": "Logout realizado com sucesso."}


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
    user_update: UserUpdate,
    user: Annotated[models.User, Depends(AuthController.get_user_from_token)],
    controller: Annotated[UserController, Depends(UserController.inject_controller)],
    has_permission: Annotated[bool, Depends(AuthController.get_permission_dependency("update_user"))]
):

    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Não possui permissão.")

    return await controller.update_user(user_update, user=user)


@app.post("/recovery-password", status_code=status.HTTP_200_OK)
@limiter.limit("5/minute")
async def post_recovery_password(
    request: Request,
    user_email: Annotated[str, Body(embed=True)],
    controller: Annotated[AuthController, Depends(AuthController.inject_controller)]
):
    await controller.recovery_password(user_email)
    return {"detail": "Se o e-mail estiver cadastrado, você receberá um link de redefinição em breve."}


@app.post("/reset-password", status_code=status.HTTP_200_OK)
async def post_reset_password(
    token: Annotated[str, Body()],
    new_password: Annotated[str, Body()],
    controller: Annotated[AuthController, Depends(AuthController.inject_controller)]
):
    await controller.reset_password(token, new_password)
    return {"detail": "Senha redefinida com sucesso."}


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
    feature: GeoJSONInput,  # Accept either Feature or FeatureCollection
    energy_type: str,
    user: Annotated[models.User, Depends(AuthController.get_user_from_token)],
    controller: Annotated[ProcessController, Depends(ProcessController.inject_controller)],
    has_permission: Annotated[bool, Depends(AuthController.get_permission_dependency("view_dash_data"))]
):
    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Não possui permissão.")

    # Check if the input is a FeatureCollection or a single Feature
    if isinstance(feature, FeatureCollection):
        # Process each feature in the collection
        results = []
        for single_feature in feature.features:
            result = await controller.dash_data(single_feature, energy_type)
            results.append(result)
        return results  # Return a list of encrypted results for each feature

    return await controller.dash_data(feature, energy_type)


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
    x: int,
    y: int,
    z: int,
    controller: Annotated[GeoFilesController, Depends(GeoFilesController.inject_controller)],
    has_permission: Annotated[bool, Depends(AuthController.get_permission_dependency("view_raster"))]
):

    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Não possui permissão.")

    return await controller.get_raster(table_name=table_name, x=x, y=y, z=z)


@app.post("/file",
          response_model=models.PdfFile,
          response_model_exclude={"updated_at", "deleted_at"})
async def post_file(
    user: Annotated[models.User | models.AnonymousUser, Depends(AuthController.get_user_from_token)],
    controller: Annotated[MediaController, Depends(MediaController.inject_controller)],
    has_permission: Annotated[bool, Depends(AuthController.get_permission_dependency("upload_pdf"))],
    name: str = Form(...),
    path: str = Form(...),
    category: str = Form(...),
    sub_category: str = Form(...),
    file: UploadFile | None = Form(None)
):
    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Não possui permissão.")

    try:
        data = {
            "name": name,
            "path": path,
            "category": category,
            "sub_category": sub_category
        }
        media_data = MediaCreate(**data)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="JSON inválido")

    return await controller.create_file(media_data, file)


@app.get("/file/{id}",
         response_model=models.PdfFile,
         response_model_exclude={"updated_at", "deleted_at"})
async def get_file(
    id: str,
    user: Annotated[models.User | models.AnonymousUser, Depends(AuthController.get_user_from_token)],
    controller: Annotated[MediaController, Depends(MediaController.inject_controller)],
    has_permission: Annotated[bool, Depends(AuthController.get_permission_dependency("get_pdf"))]
):
    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Não possui permissão.")

    return await controller.get_file(id)


@app.get("/file", response_model=list[models.PdfFile])
async def list_file(
    user: Annotated[models.User | models.AnonymousUser, Depends(AuthController.get_user_from_token)],
    controller: Annotated[MediaController, Depends(MediaController.inject_controller)],
    has_permission: Annotated[bool, Depends(AuthController.get_permission_dependency("get_pdf"))],
    category_name: str | None = None,
    sub_category_name: str | None = None,
    filter_map: bool = False
):
    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Não possui permissão.")

    return await controller.list_file(category_name, filter_map, sub_category_name)


@app.put("/file/{id}",
            response_model=models.PdfFile,
            response_model_exclude={"created_at", "updated_at", "deleted_at"},
            status_code=status.HTTP_200_OK)
async def update_file(
    id: str,
    file_update: MediaUpdate,
    user: Annotated[models.User | models.AnonymousUser, Depends(AuthController.get_user_from_token)],
    controller: Annotated[MediaController, Depends(MediaController.inject_controller)],
    has_permission: Annotated[bool, Depends(AuthController.get_permission_dependency("update_pdf"))]
):

    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Não possui permissão.")

    return await controller.update_file(file_update, id)


@app.delete("/file/{id}")
async def delete_file(
    id: str,
    user: Annotated[models.User | models.AnonymousUser, Depends(AuthController.get_user_from_token)],
    controller: Annotated[MediaController, Depends(MediaController.inject_controller)],
    has_permission: Annotated[bool, Depends(AuthController.get_permission_dependency("delete_pdf"))]
):

    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Não possui permissão.")

    return await controller.delete_file(id)


@app.post("/anonymous", status_code=status.HTTP_201_CREATED)
async def post_anonymous(
    response: Response,
    ocupation: Annotated[OcupationEnum, Body(embed=True)],
    controller: Annotated[AuthController, Depends(AuthController.inject_controller)]
):
    token = await controller.create_anonymous_user(ocupation=ocupation)
    access_max_age = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 60)) * 60
    refresh_max_age = int(os.getenv("REFRESH_TOKEN_EXPIRE_MINUTES", 1440)) * 60
    ck = _cookie_kwargs()
    response.set_cookie("access_token", token.access_token, max_age=access_max_age, **ck)
    response.set_cookie("refresh_token", token.refresh_token, max_age=refresh_max_age, **ck)
    return {"detail": "ok"}


@app.post("/contact",
          response_model=models.Feedback,
          response_model_exclude={"updated_at", "deleted_at"})
async def post_contact(
    contact: FeedbackCreate,
    controller: Annotated[FeedbackController, Depends(FeedbackController.inject_controller)]
):

    return await controller.create_feedback(contact)


@app.put("/geofiles/upload/{table_name}", status_code=status.HTTP_200_OK)
async def upload_geofile(
    table_name: str,
    file: Annotated[UploadFile, File(...)],
    controller: Annotated[GeoFilesController, Depends(GeoFilesController.inject_controller)],
    user: Annotated[models.User | models.AnonymousUser, Depends(AuthController.get_user_from_token)],
    has_permission: Annotated[bool, Depends(AuthController.get_permission_dependency("post_geofile"))]
):

    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Não possui permissão.")

    return await _save_raster_upload(table_name, file, controller)


@app.post("/raster/{raster_name}", status_code=status.HTTP_201_CREATED)
async def post_raster(
    raster_name: str,
    file: Annotated[UploadFile, File(...)],
    controller: Annotated[GeoFilesController, Depends(GeoFilesController.inject_controller)],
    has_permission: Annotated[bool, Depends(AuthController.get_permission_dependency("post_geofile"))]
):

    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Não possui permissão.")

    return await _save_raster_upload(raster_name, file, controller)


@app.get("/users",
          response_model=List[models.UserListResponse],
          status_code=status.HTTP_200_OK)
async def get_users_list(
    user: Annotated[models.User | models.AnonymousUser, Depends(AuthController.get_user_from_token)],
    controller: Annotated[UserController, Depends(UserController.inject_controller)],
    has_permission: Annotated[bool, Depends(AuthController.get_permission_dependency("get_user_list"))]
):

    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Não possui permissão.")

    return await controller.get_all_users()


@app.get("/user",
          response_model=models.User,
          response_model_exclude={"password", "updated_at", "deleted_at"},
          status_code=status.HTTP_200_OK)
async def get_user(
    user: Annotated[models.User | models.AnonymousUser, Depends(AuthController.get_user_from_token)],
    controller: Annotated[UserController, Depends(UserController.inject_controller)],
):

    return user


@app.get("/user/{id}",
          response_model=models.User,
          response_model_exclude={"password", "updated_at", "deleted_at"},
          status_code=status.HTTP_200_OK)
async def get_user_by_id(
    id: str,
    user: Annotated[models.User | models.AnonymousUser, Depends(AuthController.get_user_from_token)],
    controller: Annotated[UserController, Depends(UserController.inject_controller)],
    has_permission: Annotated[bool, Depends(AuthController.get_permission_dependency("get_user"))],
):

    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Não possui permissão.")

    return await controller.get_user_by_id(id)


@app.put("/user/{id}",
          response_model=models.User,
          response_model_exclude={"password", "created_at", "updated_at", "deleted_at"},
          status_code=status.HTTP_200_OK)
async def update_user(
    id: str,
    user_update: dict,
    user: Annotated[models.User, Depends(AuthController.get_user_from_token)],
    controller: Annotated[UserController, Depends(UserController.inject_controller)],
    has_permission: Annotated[bool, Depends(AuthController.get_permission_dependency("update_other_user"))]
):

    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Não possui permissão.")

    return await controller.update_user(user_update, id=id)


@app.post("/permission",
          response_model=models.Permission,
          response_model_exclude={"created_at", "updated_at", "deleted_at"},
          status_code=status.HTTP_200_OK)
async def create_permission(
    permission: dict,
    user: Annotated[models.User, Depends(AuthController.get_user_from_token)],
    controller: Annotated[UserController, Depends(UserController.inject_controller)],
    has_permission: Annotated[bool, Depends(AuthController.get_permission_dependency("create_permission"))]
):

    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Não possui permissão.")

    return await controller.create_permission(permission)


@app.post("/group",
          response_model=models.Group,
          response_model_exclude={"created_at", "updated_at", "deleted_at"},
          status_code=status.HTTP_200_OK)
async def create_group(
    group: dict,
    user: Annotated[models.User, Depends(AuthController.get_user_from_token)],
    controller: Annotated[UserController, Depends(UserController.inject_controller)],
    has_permission: Annotated[bool, Depends(AuthController.get_permission_dependency("create_group"))]
):

    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Não possui permissão.")

    return await controller.create_group(group)


@app.put("/group/{group_id}/add",
          response_model=models.Group,
          response_model_exclude={"created_at", "updated_at", "deleted_at"},
          status_code=status.HTTP_200_OK)
async def add_permissions_to_group(
    group_id: str,
    permissions: dict,
    user: Annotated[models.User, Depends(AuthController.get_user_from_token)],
    controller: Annotated[UserController, Depends(UserController.inject_controller)],
    has_permission: Annotated[bool, Depends(AuthController.get_permission_dependency("edit_group"))]
):

    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Não possui permissão.")

    return await controller.add_permissions_to_group(group_id, permissions['permissions'])


@app.put("/group/{group_id}/remove",
          response_model=models.Group,
          response_model_exclude={"created_at", "updated_at", "deleted_at"},
          status_code=status.HTTP_200_OK)
async def remove_permissions_to_group(
    group_id: str,
    permissions: dict,
    user: Annotated[models.User, Depends(AuthController.get_user_from_token)],
    controller: Annotated[UserController, Depends(UserController.inject_controller)],
    has_permission: Annotated[bool, Depends(AuthController.get_permission_dependency("edit_group"))]
):

    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Não possui permissão.")

    return await controller.remove_permissions_to_group(group_id, permissions['permissions'])


@app.get("/dashboard/user", status_code=status.HTTP_200_OK)
async def get_user_dashboard_data(
    controller: Annotated[UserController, Depends(UserController.inject_controller)]
):

    return await controller.get_user_dashboard_data()

@app.post("/layer-group",
    response_model=models.LayerGroups,
    response_model_exclude={"created_at", "updated_at", "deleted_at"},
    status_code=status.HTTP_200_OK
)
async def create_layer_group(group: LayerGroupCreate,
    controller: Annotated[LayersController, Depends(LayersController.inject_controller)],
    user: Annotated[models.User | models.AnonymousUser, Depends(AuthController.get_user_from_token)],
    has_permission: Annotated[bool, Depends(AuthController.get_permission_dependency("layer_admin"))]
):

    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Não possui permissão.")

    return await controller.create_layer_group(group)

@app.post(
    "/layer",
    response_model=models.Layer,
    response_model_exclude={"created_at", "updated_at", "deleted_at"},
    status_code=status.HTTP_200_OK
)
async def create_layer(
    request: Request,
    controller: Annotated[LayersController, Depends(LayersController.inject_controller)],
    name: Annotated[str, Form(...)],
    file: Annotated[UploadFile, File(...)],
    file_icon: Annotated[UploadFile, File(...)],
    subtitle: Annotated[str, Form(...)],
    layer_group_id: Annotated[Optional[str], Form(...)],
    activated: Annotated[bool, Form(...)],
    user: Annotated[models.User | models.AnonymousUser, Depends(AuthController.get_user_from_token)],
    has_permission: Annotated[bool, Depends(AuthController.get_permission_dependency("layer_admin"))]
):
    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Não possui permissão.")

    try:
        data = {
            "name": name,
            "layer_group_id": layer_group_id,
            "subtitle": subtitle,
            "activated": activated
        }
        media_data = LayerCreate(**data)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="JSON inválido")

    result = await controller.create_layer(media_data, file, file_icon)
    _bind_layer_event_context(request, result)
    return result

@app.put(
    "/layer/{id}",
    response_model=models.Layer,
    response_model_exclude={"created_at", "updated_at", "deleted_at"},
    status_code=status.HTTP_200_OK
)
async def update_layer(
    id: str,
    request: Request,
    controller: Annotated[LayersController, Depends(LayersController.inject_controller)],
    name: Annotated[str, Form(...)],
    file: Annotated[UploadFile, File(...)],
    file_icon: Annotated[UploadFile, File(...)],
    subtitle: Annotated[str, Form(...)],
    layer_group_id: Annotated[Optional[str], Form(...)],
    activated: Annotated[bool, Form(...)],
    user: Annotated[models.User | models.AnonymousUser, Depends(AuthController.get_user_from_token)],
    has_permission: Annotated[bool, Depends(AuthController.get_permission_dependency("layer_admin"))]
):
    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Não possui permissão.")

    try:
        data = {
            "name": name,
            "layer_group_id": layer_group_id,
            "subtitle": subtitle,
            "activated": activated
        }
        media_data = LayerCreate(**data)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="JSON inválido")

    result = await controller.update_layer(media_data, file, file_icon, id)
    _bind_layer_event_context(request, result)
    return result

@app.get(
    "/layer-group",
    response_model=list[dict],
    response_model_exclude={"created_at", "updated_at", "deleted_at"},
    status_code=status.HTTP_200_OK
)
async def get_layer_groups(
    controller: Annotated[LayersController, Depends(LayersController.inject_controller)],
):
    return await controller.get_layer_groups()

@app.get(
    "/layer-group/all",
    response_model=list[models.LayerGroups],
    response_model_exclude={"created_at", "updated_at", "deleted_at"},
    status_code=status.HTTP_200_OK
)
async def get_layer_groups_all(
    controller: Annotated[LayersController, Depends(LayersController.inject_controller)],
):
    return await controller.get_all_layer_groups()

@app.post(
    "/layer/{layer_id}/popup",
    response_model=dict,
    response_model_exclude={"created_at", "updated_at", "deleted_at"},
    status_code=status.HTTP_200_OK
)
async def get_layer_popup(
    layer_id: str, 
    controller: Annotated[LayersController, Depends(LayersController.inject_controller)], 
    fields: dict,
    user: Annotated[models.User | models.AnonymousUser, Depends(AuthController.get_user_from_token)],
    has_permission: Annotated[bool, Depends(AuthController.get_permission_dependency("layer_admin"))]
    ):
    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Não possui permissão.")
    
    return await controller.create_layer_popup(layer_id, fields)

@app.post(
    "/layer/{layer_id}/style",
    response_model=dict,
    response_model_exclude={"created_at", "updated_at", "deleted_at"},
    status_code=status.HTTP_200_OK
)
async def layer_style(
    layer_id: str, 
    controller: Annotated[LayersController, Depends(LayersController.inject_controller)], 
    user: Annotated[models.User | models.AnonymousUser, Depends(AuthController.get_user_from_token)],
    fields: dict,
    has_permission: Annotated[bool, Depends(AuthController.get_permission_dependency("layer_admin"))]
):
    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Não possui permissão.")

    return await controller.create_layer_style(layer_id, fields)

@app.put("/layer-group/{id}",
    response_model=models.LayerGroups,
    response_model_exclude={"created_at", "updated_at", "deleted_at"},
    status_code=status.HTTP_200_OK
)
async def update_layer_group(
    id: str,
    group: LayerGroupCreate,
    controller: Annotated[LayersController, Depends(LayersController.inject_controller)],
    user: Annotated[models.User | models.AnonymousUser, Depends(AuthController.get_user_from_token)],
    has_permission: Annotated[bool, Depends(AuthController.get_permission_dependency("layer_admin"))]
):

    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Não possui permissão.")

    return await controller.update_layer_group(group, id)

@app.delete("/layer-group/{id}",
    response_model=models.LayerGroups,
    response_model_exclude={"created_at", "updated_at", "deleted_at"},
    status_code=status.HTTP_200_OK
)
async def delete_layer_group(
    id: str,
    controller: Annotated[LayersController, Depends(LayersController.inject_controller)],
    user: Annotated[models.User | models.AnonymousUser, Depends(AuthController.get_user_from_token)],
    has_permission: Annotated[bool, Depends(AuthController.get_permission_dependency("layer_admin"))]
):

    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Não possui permissão.")

    return await controller.delete_layer_group(id)

@app.delete("/layer/{id}",
    response_model=models.Layer,
    response_model_exclude={"created_at", "updated_at", "deleted_at"},
    status_code=status.HTTP_200_OK
)
async def delete_layer(
    id: str,
    controller: Annotated[LayersController, Depends(LayersController.inject_controller)],
    user: Annotated[models.User | models.AnonymousUser, Depends(AuthController.get_user_from_token)],
    has_permission: Annotated[bool, Depends(AuthController.get_permission_dependency("layer_admin"))]
):

    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Não possui permissão.")

    return await controller.delete_layer(id)

@app.get("/layer/{id}",
    response_model=dict,
    response_model_exclude={"created_at", "updated_at", "deleted_at"},
    status_code=status.HTTP_200_OK
)
async def get_layer_id(
    id: str,
    controller: Annotated[LayersController, Depends(LayersController.inject_controller)],
    user: Annotated[models.User | models.AnonymousUser, Depends(AuthController.get_user_from_token)],
    has_permission: Annotated[bool, Depends(AuthController.get_permission_dependency("layer_admin"))]
):

    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Não possui permissão.")

    return await controller.get_layer_by_id(id)


@app.get(
    "/layer/{layer_id}/data",
    status_code=status.HTTP_200_OK,
)
async def get_layer_geojson_data(
    layer_id: str,
    controller: Annotated[LayersController, Depends(LayersController.inject_controller)],
):
    """Serve layer GeoJSON file for map display (tracked for analytics)."""
    from fastapi.responses import FileResponse

    layer = await controller.repository.get_layer_by_id(layer_id)
    if not layer or not layer.path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Camada não encontrada")
    file_path = resolve_storage_path(layer.path)
    if file_path is None or not file_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Arquivo da camada não encontrado")
    return FileResponse(file_path, media_type="application/json")


@app.post(
    "/layer/upload-preview",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def track_layer_upload_preview(
    payload: LayerUploadPreviewPayload,
    request: Request,
    user: Annotated[models.User | models.AnonymousUser, Depends(AuthController.get_user_from_token)],
):
    tracker = getattr(request.state, "admin_analytics_tracker", None)
    if tracker is not None:
        tracker.bind_actor(user)

    request.state.layer_event_context = {
        "layer_name": payload.file_name,
        "group_id": None,
    }
    request.state.layer_upload_details = {
        "feature_count": payload.feature_count,
        "geometry_types": sorted({geometry_type for geometry_type in payload.geometry_types if geometry_type}),
    }
    request.state.layer_preview_geojson = payload.geojson
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.post("/data-station",
    response_model=models.DataStation,
    status_code=status.HTTP_201_CREATED
)
async def create_data_station(
    create_data_station: CreateDataStation,
    user: models.User | models.AnonymousUser = Depends(AuthController.get_user_from_token),
    has_permission: bool = Depends(AuthController.get_permission_dependency("layer_admin")),
    controller: PlatformService = Depends(PlatformService.inject_service)):
    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Não possui permissão.")
    try:
        station: models.DataStation = await controller.create_data_station(create_data_station)
        return station
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except (RuntimeError, Exception) as e:
        logging.exception("Erro ao criar estação")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Erro interno do servidor.")


@app.get('/data-station', response_model=list[models.DataStation])
async def list_data_station(
    name: str | None = Query(None, description="Nome exato da estação"),
    layer_id: UUID | None = Query(None, description="Identificador da camada da estação"),
    station_type: UUID | None = Query(None, alias="type", description="Identificador do tipo da estação"),
    user: models.User | models.AnonymousUser = Depends(AuthController.get_user_from_token),
    controller: PlatformService = Depends(PlatformService.inject_service)
):
    try:
        return await controller.list_data_stations(name=name, layer_id=layer_id, station_type=station_type)
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))# NÃO LOCALIZADO
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))# DADO INVÁLIDO
    except Exception:
        logging.exception("Erro ao listar estações")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Erro interno do servidor.")# Erro desconhecido


@app.get("/admin-analytics/filter-options")
async def get_admin_analytics_filter_options(
    request: Request,
    user: Annotated[models.User | models.AnonymousUser, Depends(AuthController.get_user_from_token)],
    controller: Annotated[AdminAnalyticsController, Depends(AdminAnalyticsController.inject_controller)],
):
    await controller.assert_admin(user)
    query: AdminAnalyticsFilterOptionsQuery = controller.parse_query(AdminAnalyticsFilterOptionsQuery, request.query_params)
    return await controller.get_filter_options(query)


@app.get("/admin-analytics/overview")
async def get_admin_analytics_overview(
    request: Request,
    user: Annotated[models.User | models.AnonymousUser, Depends(AuthController.get_user_from_token)],
    controller: Annotated[AdminAnalyticsController, Depends(AdminAnalyticsController.inject_controller)],
):
    await controller.assert_admin(user)
    query: AdminAnalyticsOverviewQuery = controller.parse_query(AdminAnalyticsOverviewQuery, request.query_params)
    return await controller.get_overview(query)


@app.get("/admin-analytics/user-activity")
async def get_admin_analytics_user_activity(
    request: Request,
    user: Annotated[models.User | models.AnonymousUser, Depends(AuthController.get_user_from_token)],
    controller: Annotated[AdminAnalyticsController, Depends(AdminAnalyticsController.inject_controller)],
):
    await controller.assert_admin(user)
    query: AdminAnalyticsUserActivityQuery = controller.parse_query(AdminAnalyticsUserActivityQuery, request.query_params)
    return await controller.get_user_activity(query)


@app.get("/admin-analytics/user-activity/{user_id}")
async def get_admin_analytics_user_activity_detail(
    user_id: str,
    request: Request,
    user: Annotated[models.User | models.AnonymousUser, Depends(AuthController.get_user_from_token)],
    controller: Annotated[AdminAnalyticsController, Depends(AdminAnalyticsController.inject_controller)],
):
    await controller.assert_admin(user)
    query: AdminAnalyticsUserActivityQuery = controller.parse_query(AdminAnalyticsUserActivityQuery, request.query_params)
    return await controller.get_user_activity_detail(user_id, query)


@app.get("/admin-analytics/file-usage")
async def get_admin_analytics_file_usage(
    request: Request,
    user: Annotated[models.User | models.AnonymousUser, Depends(AuthController.get_user_from_token)],
    controller: Annotated[AdminAnalyticsController, Depends(AdminAnalyticsController.inject_controller)],
):
    await controller.assert_admin(user)
    query: AdminAnalyticsFileUsageQuery = controller.parse_query(AdminAnalyticsFileUsageQuery, request.query_params)
    return await controller.get_file_usage(query)


@app.get("/admin-analytics/file-usage/{file_id}")
async def get_admin_analytics_file_usage_detail(
    file_id: str,
    request: Request,
    user: Annotated[models.User | models.AnonymousUser, Depends(AuthController.get_user_from_token)],
    controller: Annotated[AdminAnalyticsController, Depends(AdminAnalyticsController.inject_controller)],
):
    await controller.assert_admin(user)
    query: AdminAnalyticsFileUsageQuery = controller.parse_query(AdminAnalyticsFileUsageQuery, request.query_params)
    return await controller.get_file_usage_detail(file_id, query)


@app.get("/admin-analytics/map-usage")
async def get_admin_analytics_map_usage(
    request: Request,
    user: Annotated[models.User | models.AnonymousUser, Depends(AuthController.get_user_from_token)],
    controller: Annotated[AdminAnalyticsController, Depends(AdminAnalyticsController.inject_controller)],
):
    await controller.assert_admin(user)
    query: AdminAnalyticsMapUsageQuery = controller.parse_query(AdminAnalyticsMapUsageQuery, request.query_params)
    return await controller.get_map_usage(query)


@app.get("/admin-analytics/map-usage/{layer_id}")
async def get_admin_analytics_map_usage_detail(
    layer_id: str,
    request: Request,
    user: Annotated[models.User | models.AnonymousUser, Depends(AuthController.get_user_from_token)],
    controller: Annotated[AdminAnalyticsController, Depends(AdminAnalyticsController.inject_controller)],
):
    await controller.assert_admin(user)
    query: AdminAnalyticsMapUsageQuery = controller.parse_query(AdminAnalyticsMapUsageQuery, request.query_params)
    return await controller.get_map_usage_detail(layer_id, query)


@app.get("/admin-analytics/admin-operations")
async def get_admin_analytics_admin_operations(
    request: Request,
    user: Annotated[models.User | models.AnonymousUser, Depends(AuthController.get_user_from_token)],
    controller: Annotated[AdminAnalyticsController, Depends(AdminAnalyticsController.inject_controller)],
):
    await controller.assert_admin(user)
    query: AdminAnalyticsAdminOperationsQuery = controller.parse_query(AdminAnalyticsAdminOperationsQuery, request.query_params)
    return await controller.get_admin_operations(query)


@app.get("/admin-analytics/admin-operations/{event_id}")
async def get_admin_analytics_admin_operation_detail(
    event_id: str,
    request: Request,
    user: Annotated[models.User | models.AnonymousUser, Depends(AuthController.get_user_from_token)],
    controller: Annotated[AdminAnalyticsController, Depends(AdminAnalyticsController.inject_controller)],
):
    await controller.assert_admin(user)
    query: AdminAnalyticsAdminOperationsQuery = controller.parse_query(AdminAnalyticsAdminOperationsQuery, request.query_params)
    return await controller.get_admin_operation_detail(event_id, query)


@app.get("/admin-analytics/system-health")
async def get_admin_analytics_system_health(
    request: Request,
    user: Annotated[models.User | models.AnonymousUser, Depends(AuthController.get_user_from_token)],
    controller: Annotated[AdminAnalyticsController, Depends(AdminAnalyticsController.inject_controller)],
):
    await controller.assert_admin(user)
    query: AdminAnalyticsSystemHealthQuery = controller.parse_query(AdminAnalyticsSystemHealthQuery, request.query_params)
    return await controller.get_system_health(query)


@app.get("/admin-analytics/system-health/{endpoint_key}")
async def get_admin_analytics_system_health_detail(
    endpoint_key: str,
    request: Request,
    user: Annotated[models.User | models.AnonymousUser, Depends(AuthController.get_user_from_token)],
    controller: Annotated[AdminAnalyticsController, Depends(AdminAnalyticsController.inject_controller)],
):
    await controller.assert_admin(user)
    query: AdminAnalyticsSystemHealthQuery = controller.parse_query(AdminAnalyticsSystemHealthQuery, request.query_params)
    return await controller.get_system_health_detail(endpoint_key, query)


@app.post("/admin-analytics/export")
async def post_admin_analytics_export(
    user: Annotated[models.User | models.AnonymousUser, Depends(AuthController.get_user_from_token)],
    controller: Annotated[AdminAnalyticsController, Depends(AdminAnalyticsController.inject_controller)],
    payload: dict = Body(...),
) -> StreamingResponse:
    await controller.assert_admin(user)
    export_request: AdminAnalyticsExportRequest = controller.parse_body(AdminAnalyticsExportRequest, payload)
    return await controller.generate_export_file(export_request)


@app.get("/admin-analytics/export/download")
async def get_admin_analytics_export_download(
    user: Annotated[models.User | models.AnonymousUser, Depends(AuthController.get_user_from_token)],
    controller: Annotated[AdminAnalyticsController, Depends(AdminAnalyticsController.inject_controller)],
    payload: str = Query(..., description="Base64-encoded JSON export request"),
) -> StreamingResponse:
    """Browser-navigation endpoint: cookies are sent automatically and Content-Disposition triggers
    a native save dialog without needing a user-gesture-safe JS click."""
    await controller.assert_admin(user)
    try:
        decoded = base64.b64decode(payload).decode("utf-8")
        payload_dict = json.loads(decoded)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Payload inválido.")
    export_request: AdminAnalyticsExportRequest = controller.parse_body(AdminAnalyticsExportRequest, payload_dict)
    return await controller.generate_export_file(export_request)


@app.get("/admin-analytics/export/{export_id}")
async def get_admin_analytics_export(
    export_id: str,
    user: Annotated[models.User | models.AnonymousUser, Depends(AuthController.get_user_from_token)],
    controller: Annotated[AdminAnalyticsController, Depends(AdminAnalyticsController.inject_controller)],
):
    await controller.assert_admin(user)
    return await controller.get_export(export_id)


@app.get('/data-station/{id}/heights', summary="Lista de alturas para uma estação lidar",     description="""
Retorna a lista de alturas disponíveis para uma estação lidar dentro de um intervalo de datas.

- `start_datetime`: data/hora inicial da consulta
- `end_datetime`: data/hora final da consulta

Caso as datas não sejam informadas, serão utilizados os dados do último mês salvo.
""" 
)
async def get_heights_in_data_station(
    id: UUID = PathParam(..., description="Identificador da estação"),
    start_datetime: datetime|None = Query(None, description="Data/hora inicial", example="2026-01-10T00:00:00"),
    end_datetime: datetime|None = Query(None, description="Data/hora final", example="2026-01-10T23:50:00"), 
    user: models.User | models.AnonymousUser = Depends(AuthController.get_user_from_token),
    controller: PlatformService = Depends(PlatformService.inject_service)
):
    try:
        heights = await controller.heightsInPlatform(id, start_datetime, end_datetime )
        return heights
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))# NÃO LOCALIZADO
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))# DADO INVÁLIDO
    except Exception:
        logging.exception("Erro ao listar alturas da estação")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Erro interno do servidor.")# Erro desconhecido


@app.get('/data-station/{id}/available-months', summary="Lista os meses disponíveis para uma estação")
async def get_available_months_in_data_station(
    id: UUID = PathParam(..., description="Identificador da estação"),
    user: models.User | models.AnonymousUser = Depends(AuthController.get_user_from_token),
    controller: PlatformService = Depends(PlatformService.inject_service)
):
    try:
        return await controller.list_available_months(id)
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception:
        logging.exception("Erro ao listar meses disponíveis da estação")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Erro interno do servidor.")


@app.post("/lidar/{id}", summary="Salvar dados mensais de uma estação lidar", description=
"""
Recebe um arquivo CSV contendo os dados qualificados da estação lidar para processamento.

Regras do arquivo:
- O CSV deve utilizar `;` como separador de colunas.
- O separador `,` é utilizado para valores decimais.
- A função realiza automaticamente a conversão dos valores numéricos.

Processamento:
- Os dados enviados são processados em segundo plano.
- Os registros são consolidados e salvos em média horária.

Retorno:
- A API retorna imediatamente o status de processamento do arquivo.
""" 
)
async def upload_lidar_data(
    background_tasks: BackgroundTasks,
    id: UUID = PathParam(..., description="Identificador da estação"),
    file: UploadFile = File(...),
    user: models.User | models.AnonymousUser = Depends(AuthController.get_user_from_token),
    has_permission: bool = Depends(AuthController.get_permission_dependency("layer_admin")), 
    controller: PlatformService = Depends(PlatformService.inject_service)
):
    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Não possui permissão.")

    if not file.filename.lower().endswith('.csv'):
        raise HTTPException( status_code=status.HTTP_400_BAD_REQUEST, detail="Somente arquivos .csv são aceitos.")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name
    try:
        df = pd.read_csv(tmp_path, header=0, sep=";", )
        await controller.validate_lidar_data_columns(df.head())

        background_tasks.add_task(controller.create_lidar_data_month, tmp_path, id)
        return JSONResponse( status_code=status.HTTP_202_ACCEPTED, content={"status": "processando", "message": f"O arquivo '{file.filename}' foi recebido e está sendo processado em segundo plano."})
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))# DADO INVÁLIDO
    except Exception:
        logging.exception("Erro ao processar arquivo CSV")
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Arquivo CSV inválido ou incompatível.")# Erro desconhecido


@app.delete("/lidar/{id}" ,  summary="Deleta os dados lidar de uma estação entre duas datas e horários.")
async def delete_lidar_data(
    id: UUID = PathParam(..., description="Identificador da estação"),
    start_datetime: datetime = Query(..., description="Data/hora inicial", example="2026-01-10T00:00:00"),
    end_datetime: datetime = Query(..., description="Data/hora final", example="2026-01-01T23:50:00"),
    user: models.User | models.AnonymousUser = Depends(AuthController.get_user_from_token),
    has_permission: bool = Depends(AuthController.get_permission_dependency("layer_admin")),
    controller: PlatformService = Depends(PlatformService.inject_service)
):
    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Não possui permissão.")
    try:
        await controller.delete_qualified_data_between_datetimes(id, start_datetime, end_datetime)
        return JSONResponse(status_code=status.HTTP_202_ACCEPTED, content={"status": "success", "message": "Dados lidar deletados com sucesso."})
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))# NÃO LOCALIZADO
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))# DADO INVÁLIDO
    except Exception:
        logging.exception("Erro ao deletar dados lidar")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Erro interno do servidor.")# Erro desconhecido


@app.post("/solarimetric-stations/{id}", summary="Salvar dados mensais de uma estação solarimétrica")
async def upload_solarimetric_station_data(
    background_tasks: BackgroundTasks,
    id: UUID = PathParam(..., description="Identificador da estação"),
    file: UploadFile = File(...),
    user: models.User | models.AnonymousUser = Depends(AuthController.get_user_from_token),
    has_permission: bool = Depends(AuthController.get_permission_dependency("layer_admin")),
    controller: PlatformService = Depends(PlatformService.inject_service)
):
    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Não possui permissão.")

    if not file.filename.lower().endswith('.csv'):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Somente arquivos .csv são aceitos.")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name
    try:
        df = pd.read_csv(tmp_path, header=0)
        await controller.validate_solarimetric_data_columns(df.head())

        background_tasks.add_task(controller.create_solarimetric_data_month, tmp_path, id)
        return JSONResponse(status_code=status.HTTP_202_ACCEPTED, content={"status": "processando", "message": f"O arquivo '{file.filename}' foi recebido e está sendo processado em segundo plano."})
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except Exception:
        logging.exception("Erro ao processar arquivo CSV solarimétrico")
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Arquivo CSV inválido ou incompatível.")


@app.delete("/solarimetric-stations/{id}" , summary="Deleta os dados solarimétricos de uma estação entre duas datas e horários.")
async def delete_solarimetric_station_data(
    id: UUID = PathParam(..., description="Identificador da estação"),
    start_datetime: datetime = Query(..., description="Data/hora inicial", example="2026-01-10T00:00:00"),
    end_datetime: datetime = Query(..., description="Data/hora final", example="2026-01-01T23:50:00"),
    user: models.User | models.AnonymousUser = Depends(AuthController.get_user_from_token),
    has_permission: bool = Depends(AuthController.get_permission_dependency("layer_admin")),
    controller: PlatformService = Depends(PlatformService.inject_service)
):
    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Não possui permissão.")
    try:
        await controller.delete_solarimetric_data_between_datetimes(id, start_datetime, end_datetime)
        return JSONResponse(status_code=status.HTTP_202_ACCEPTED, content={"status": "success", "message": "Dados solarimétricos deletados com sucesso."})
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception:
        logging.exception("Erro ao deletar dados solarimétricos")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Erro interno do servidor.")


@app.get("/time-series/{id}" ,  summary="Série temporal de um campo de uma estação entre duas datas e horários.")
async def time_series_list_data_by_field_between_datetimes(
    id: UUID = PathParam(..., description="Identificador da estação"),
    col: str = Query(..., description="Nome do campo" ),
    start_datetime: datetime| None = Query(None, description="Data/hora inicial", example="2026-01-10T00:00:00"),
    end_datetime: datetime|None = Query(None, description="Data/hora final", example="2026-01-10T23:50:00"),
    user: models.User | models.AnonymousUser = Depends(AuthController.get_user_from_token),
    controller: PlatformService = Depends(PlatformService.inject_service)
):
    try:
        return await controller.graphics_time_series_by_station(id, col, start_datetime, end_datetime)
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))# NÃO LOCALIZADO
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))# DADO INVÁLIDO
    except Exception:
        logging.exception("Erro ao gerar série temporal")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Erro interno do servidor.")# Erro desconhecido


@app.get("/wind-rose/{id}" ,  summary="Rosa dos ventos com base nos dados de uma estação lidar entre duas datas e horários.")
async def wind_rose_data_between_datetimes(
    id: UUID = PathParam(..., description="Identificador da estação"),
    col: str = Query("h_spd", description="Campo base do gráfico"),
    start_datetime: datetime|None = Query(None, description="Data/hora inicial", example="2026-01-10T00:00:00"),
    end_datetime: datetime|None = Query(None, description="Data/hora final", example="2026-01-10T23:50:00"),
    height: int|None = Query(None, description="Altura",ge=1, example=210),
    user: models.User | models.AnonymousUser = Depends(AuthController.get_user_from_token),
    controller: PlatformService = Depends(PlatformService.inject_service)
):
    try:
        station = await controller.get_data_station(id=id)
        resolved_field = controller.resolve_field_name_for_station(station, col)
        if resolved_field == "h_spd":
            mode = WindRoseMode.mean_h_spd
        elif resolved_field == "ti":
            mode = WindRoseMode.mean_ti
        else:
            raise ValueError("A rosa dos ventos só aceita os campos 'h_spd' ou 'ti'.")
        return await controller.last_month_and_x_heights_wind_rose(id, mode, start_datetime, end_datetime, height)
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))# NÃO LOCALIZADO
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))# DADO INVÁLIDO
    except Exception:
        logging.exception("Erro ao gerar rosa dos ventos")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Erro interno do servidor.")# Erro desconhecido


@app.get("/vertical-profile/{id}" ,  summary="Perfil vertical da velocidade horizontal do vento em uma estação lidar.")
async def vertical_profile_data_between_datetimes(
    id: UUID = PathParam(..., description="Identificador da estação"),
    col: str | None = Query(None, description="Campo base do gráfico"),
    start_datetime: datetime|None = Query(None, description="Data/hora inicial", example="2026-01-10T00:00:00"),
    end_datetime: datetime|None = Query(None, description="Data/hora final", example="2026-01-10T23:50:00"),
    user: models.User | models.AnonymousUser = Depends(AuthController.get_user_from_token),
    controller: PlatformService = Depends(PlatformService.inject_service)
):
    try:
        if col is not None:
            station = await controller.get_data_station(id=id)
            resolved_field = controller.resolve_field_name_for_station(station, col)
            if resolved_field != "h_spd":
                raise ValueError("O perfil vertical só aceita o campo 'h_spd'.")
        return  await controller.average_vertical_profile( id, start_datetime, end_datetime)
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))# NÃO LOCALIZADO
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))# DADO INVÁLIDO
    except Exception:
        logging.exception("Erro ao calcular perfil vertical")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Erro interno do servidor.")# Erro desconhecido


@app.get("/diurnal-profile/{id}" ,  summary="Perfil diurno de um campo específico de uma estação entre duas datas.")
async def diurnal_profile_by_field_(
    id: UUID = PathParam(..., description="Identificador da estação"),
    col: str = Query(..., description="Nome do campo" ),
    start_datetime: datetime|None = Query(None, description="Data/hora inicial", example="2026-01-10T00:00:00"),
    end_datetime: datetime|None = Query(None, description="Data/hora final", example="2026-01-10T23:50:00"),
    user: models.User | models.AnonymousUser = Depends(AuthController.get_user_from_token),
    controller: PlatformService = Depends(PlatformService.inject_service)
):
    try:
        return  await controller.average_diurnal_cycle(id, col, start_datetime, end_datetime)
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))# NÃO LOCALIZADO
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))# DADO INVÁLIDO
    except Exception:
        logging.exception("Erro ao calcular perfil diurno")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Erro interno do servidor.")# Erro desconhecido