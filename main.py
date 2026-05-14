import os
import shutil
import tempfile
from contextlib import asynccontextmanager
from typing import Annotated, List
from uuid import UUID

import base64
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
from Crypto.Util.Padding import pad, unpad

import sentry_sdk
from dotenv import load_dotenv, find_dotenv
from fastapi import Body, Depends, BackgroundTasks, FastAPI, status, Response, UploadFile, HTTPException, Form, Body, File, Query, Path as PathParam
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import EmailStr
from typing import Union
from pathlib import Path
from typing import Optional, Annotated
import json
from datetime import datetime, time, date
import pandas as pd

from controllers.auth_controller import AuthController
from controllers.feedback_controller import FeedbackController
from controllers.geo_files_controller import GeoFilesController
from controllers.process_controller import ProcessController
from controllers.user_controller import UserController
from controllers.media_controller import MediaController
from controllers.layers_controller import LayersController
from controllers.platform_wind import PlatformService
from schemas.AdminStatusResponse import AdminStatusResponse
from schemas.layers import LayerGroupCreate, LayerCreate
from schemas.feature import Feature
from schemas.featureCollection import FeatureCollection
from schemas.feedback import FeedbackCreate
from schemas.platform_wind import CreatePlatform
from schemas.token import Token
from schemas.user import UserCreate, UserUpdate
from schemas.media import MediaCreate, MediaUpdate
from sql_app import models
from sql_app.database import init_db
from enums.ocupation_enum import OcupationEnum
from enums.platform_enum import WindRoseMode, FieldsQualifiedData


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


async def get_encryption_key():
    key_hex = os.getenv("ENCRYPTION_KEY")
    if key_hex is None:
        raise ValueError("ENCRYPTION_KEY não está definida no ambiente.")
    return bytes.fromhex(key_hex)


async def encrypt_data(data: dict) -> str:
    plaintext = json.dumps(data)

    iv = get_random_bytes(16)
    cipher = AES.new(await get_encryption_key(), AES.MODE_CBC, iv)

    ciphertext = cipher.encrypt(pad(plaintext.encode('utf-8'), AES.block_size))
    return base64.b64encode(iv + ciphertext).decode('utf-8')


async def decrypt_data(encrypted_data: str) -> dict:
    iv = encrypted_data[:16]
    ciphertext = encrypted_data[16:]

    cipher = AES.new(await get_encryption_key(), AES.MODE_CBC, iv)
    plaintext = unpad(cipher.decrypt(ciphertext), AES.block_size)

    return json.loads(plaintext.decode('utf-8'))

app = FastAPI(lifespan=lifespan)

private_directory = Path("assets/public")
private_directory.mkdir(parents=True, exist_ok=True)
app.mount("/assets/public", StaticFiles(directory="assets/public"), name="public")


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "http://127.0.0.1:8000", "http://localhost:5173", "http://127.0.0.1:5173", "https://back.plataformadeenergiasrn.com.br", "https://plataformadeenergiasrn.com.br"],
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)


GeoJSONInput = Union[Feature, FeatureCollection]


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


@app.post("/token")
async def login(
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
    user_update: UserUpdate,
    user: Annotated[models.User, Depends(AuthController.get_user_from_token)],
    controller: Annotated[UserController, Depends(UserController.inject_controller)],
    has_permission: Annotated[bool, Depends(AuthController.get_permission_dependency("update_user"))]
):

    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Não possui permissão.")

    return await controller.update_user(user_update, user=user)


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

    return await encrypt_data(await controller.process_geo_process(feature, raster_name, user.id.hex))


@app.get("/process/raster/{raster_name}")
async def post_process_raster(
    raster_name: str,
    controller: Annotated[ProcessController, Depends(ProcessController.inject_controller)],
    user: Annotated[models.User | models.AnonymousUser, Depends(AuthController.get_user_from_token)],
    has_permission: Annotated[bool, Depends(AuthController.get_permission_dependency("view_raster"))]
):

    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Não possui permissão.")

    return await encrypt_data(await controller.process_raster(raster_name, user.id.hex))


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
            results.append(await encrypt_data(result))
        return results  # Return a list of encrypted results for each feature

    return await encrypt_data(await controller.dash_data(feature, energy_type))


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
    ocupation: Annotated[OcupationEnum, Body(embed=True)],
    controller: Annotated[AuthController, Depends(AuthController.inject_controller)]
):
    return await controller.create_anonymous_user(ocupation=ocupation)


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

    return await controller.create_layer(media_data, file, file_icon)

@app.put(
    "/layer/{id}",
    response_model=models.Layer,
    response_model_exclude={"created_at", "updated_at", "deleted_at"},
    status_code=status.HTTP_200_OK
)
async def update_layer(
    id: str,
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

    return await controller.update_layer(media_data, file, file_icon, id)

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


@app.post('/platform', response_model=models.Platform, status_code=status.HTTP_201_CREATED)
async def create_platform(
    createPlatform: CreatePlatform, 
    user: models.User | models.AnonymousUser = Depends(AuthController.get_user_from_token),
    has_permission: bool = Depends(AuthController.get_permission_dependency("layer_admin")),
    controller: PlatformService = Depends(PlatformService.inject_service)):
    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Não possui permissão.")
    try:
        platform: models.Platform = await controller.create_platform(createPlatform)
        return platform
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@app.get('/platform', response_model=list[models.Platform])
async def list_platform(
    user: models.User | models.AnonymousUser = Depends(AuthController.get_user_from_token),
    has_permission: bool = Depends(AuthController.get_permission_dependency("layer_admin")),
    controller: PlatformService = Depends(PlatformService.inject_service)
):
    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Não possui permissão.")
    try:
        platform = await controller.list_platforms()
        return platform
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))# NÃO LOCALIZADO
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))# DADO INVÁLIDO
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))# Erro desconhecido


@app.get('/platform/{id}/heights', summary="Lista de alturas para uma plataforma",     description="""
Retorna a lista de alturas disponíveis para uma plataforma dentro de um intervalo de datas.

- `start_datetime`: data/hora inicial da consulta
- `end_datetime`: data/hora final da consulta

Caso as datas não sejam informadas, serão utilizados os dados do último mês salvo.
""" 
)
async def getHeightsInPlatform(
    id: UUID = PathParam(..., description="Identificador da plataforma"),
    start_datetime: datetime|None = Query(None, description="Data/hora inicial", example="2026-01-10T00:00:00"),
    end_datetime: datetime|None = Query(None, description="Data/hora final", example="2026-01-10T23:50:00"), 
    user: models.User | models.AnonymousUser = Depends(AuthController.get_user_from_token),
    has_permission: bool = Depends(AuthController.get_permission_dependency("layer_admin")),
    controller: PlatformService = Depends(PlatformService.inject_service)
):
    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Não possui permissão.")
    try:
        heights = await controller.heightsInPlatform(id, start_datetime, end_datetime )
        return heights
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))# NÃO LOCALIZADO
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))# DADO INVÁLIDO
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))# Erro desconhecido


@app.post("/qualified_data/{id}", summary="Salvar dados mensais de uma plataforma", description=
"""
Recebe um arquivo CSV contendo os dados qualificados da plataforma para processamento.

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
async def upload_qualified_data(
    background_tasks: BackgroundTasks,
    id: UUID = PathParam(..., description="Identificador da plataforma"),
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
        await controller.validate_qualified_data_columns(df.head())

        # asyncio.create_task(controller.create_qualified_data_month(tmp_path, id))
        background_tasks.add_task( controller.create_qualified_data_month, tmp_path, id) #Teste local
        return JSONResponse( status_code=status.HTTP_202_ACCEPTED, content={"status": "processando", "message": f"O arquivo '{file.filename}' foi recebido e está sendo processado em segundo plano."})
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))# DADO INVÁLIDO


@app.delete("/qualified_data/{id}" ,  summary="Deleta os dados qualificados de uma plataforma entre duas datas e horários.")
async def delete_qualified_data(
    id: UUID = PathParam(..., description="Identificador da plataforma"),
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
        return JSONResponse(status_code=status.HTTP_202_ACCEPTED, content={"status": "success", "message": "Dados qualificados deletados com sucesso."})
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))# NÃO LOCALIZADO
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))# DADO INVÁLIDO
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))# Erro desconhecido


@app.get("/time-series/platform/{id}" ,  summary="Série temporal de um campo de uma estação entre duas datas e horários.")
async def time_series_list_data_by_field_between_datetimes(
    id: UUID = PathParam(..., description="Identificador da plataforma"),
    field_name: FieldsQualifiedData = Query(..., description="Nome do campo" ),
    start_datetime: datetime| None = Query(None, description="Data/hora inicial", example="2026-01-10T00:00:00"),
    end_datetime: datetime|None = Query(None, description="Data/hora final", example="2026-01-10T23:50:00"),
    user: models.User | models.AnonymousUser = Depends(AuthController.get_user_from_token),
    has_permission: bool = Depends(AuthController.get_permission_dependency("layer_admin")),
    controller: PlatformService = Depends(PlatformService.inject_service)
):
    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Não possui permissão.")
    try:
        data = await controller.graphics_time_series_data_by_plataform(id, field_name, start_datetime, end_datetime)
        return data
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))# NÃO LOCALIZADO
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))# DADO INVÁLIDO
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))# Erro desconhecido


@app.get("/wind-rose/platform/{id}" ,  summary="Rosa dos ventos com base nos dados de uma plataforma entre duas datas e horários.")
async def wind_rose_data_between_datetimes(
    id: UUID = PathParam(..., description="Identificador da plataforma"),
    start_datetime: datetime|None = Query(None, description="Data/hora inicial", example="2026-01-10T00:00:00"),
    end_datetime: datetime|None = Query(None, description="Data/hora final", example="2026-01-10T23:50:00"),
    mode: WindRoseMode = Query( WindRoseMode.mean_h_spd, description="Modo de cálculo da rosa dos ventos"),
    height: int|None = Query(None, description="Altura",ge=1, example=210),
    user: models.User | models.AnonymousUser = Depends(AuthController.get_user_from_token),
    has_permission: bool = Depends(AuthController.get_permission_dependency("layer_admin")),
    controller: PlatformService = Depends(PlatformService.inject_service)
):
    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Não possui permissão.")
    try:
        return await controller.last_month_and_x_heights_wind_rose(id, mode, start_datetime, end_datetime, height)
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))# NÃO LOCALIZADO
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))# DADO INVÁLIDO
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))# Erro desconhecido


@app.get("/vertical-profile/platform/{id}" ,  summary="Perfil vertical da velocidade horizontal do vento em uma plataforma.")
async def vertical_profile_data_between_datetimes(
    id: UUID = PathParam(..., description="Identificador da plataforma"),
    start_datetime: datetime|None = Query(None, description="Data/hora inicial", example="2026-01-10T00:00:00"),
    end_datetime: datetime|None = Query(None, description="Data/hora final", example="2026-01-10T23:50:00"),
    user: models.User | models.AnonymousUser = Depends(AuthController.get_user_from_token),
    has_permission: bool = Depends(AuthController.get_permission_dependency("layer_admin")),
    controller: PlatformService = Depends(PlatformService.inject_service)
):
    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Não possui permissão.")
    try:
        return  await controller.average_vertical_profile( id, start_datetime, end_datetime)
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))# NÃO LOCALIZADO
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))# DADO INVÁLIDO
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))# Erro desconhecido


@app.get("/diurnal-profile/platform/{id}" ,  summary="Perfil diurno de um campo específico de uma plataforma entre duas datas.")
async def diurnal_profile_by_field_(
    id: UUID = PathParam(..., description="Identificador da plataforma"),
    field_name: FieldsQualifiedData = Query(..., description="Nome do campo" ),
    start_datetime: datetime|None = Query(None, description="Data/hora inicial", example="2026-01-10T00:00:00"),
    end_datetime: datetime|None = Query(None, description="Data/hora final", example="2026-01-10T23:50:00"),
    user: models.User | models.AnonymousUser = Depends(AuthController.get_user_from_token),
    has_permission: bool = Depends(AuthController.get_permission_dependency("layer_admin")),
    controller: PlatformService = Depends(PlatformService.inject_service)
):
    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Não possui permissão.")
    try:
        return  await controller.average_diurnal_cycle(id, field_name, start_datetime, end_datetime)
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))# NÃO LOCALIZADO
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))# DADO INVÁLIDO
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))# Erro desconhecido