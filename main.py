import os
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
from fastapi import Body, Depends, FastAPI, status, Response, UploadFile, HTTPException, Form, Body
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import EmailStr
from typing import Union
import json

from controllers.auth_controller import AuthController
from controllers.feedback_controller import FeedbackController
from controllers.geo_files_controller import GeoFilesController
from controllers.process_controller import ProcessController
from controllers.user_controller import UserController
from controllers.media_controller import MediaController
from schemas.feature import Feature
from schemas.featureCollection import FeatureCollection
from schemas.feedback import FeedbackCreate
from schemas.token import Token
from schemas.user import UserCreate, UserUpdate
from schemas.media import MediaCreate, MediaUpdate
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


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "http://127.0.0.1:8000", "http://localhost:5173", "http://127.0.0.1:5173", "https://plataforma-energias-rn-production.up.railway.app", "https://atlaseolicosolarn.com.br", "https://back.atlaseolicosolarn.com.br", "https://platenergiasrn.com.br"],
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)


GeoJSONInput = Union[Feature, FeatureCollection]


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
    pdf: str = Form(...),
    file: UploadFile | None = Form(None)
):
    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Não possui permissão.")

    try:
        data = json.loads(pdf)
        media_data = MediaCreate(**data)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="JSON inválido")

    return await controller.create_file(media_data, file)


@app.get("/file/{id}",
         response_model=models.PdfFile,
         response_model_exclude={"updated_at", "deleted_at"})
async def get_file(
    id: str,
    controller: Annotated[MediaController, Depends(MediaController.inject_controller)]
):

    return await controller.get_file(id)

@app.get("/file", response_model=list[models.PdfFile])
async def list_file(
    controller: Annotated[MediaController, Depends(MediaController.inject_controller)],
    category_name: str | None = None,
    sub_category_name: str | None = None,
    filter_map: bool = False
):
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
    file: UploadFile,
    controller: Annotated[GeoFilesController, Depends(GeoFilesController.inject_controller)],
    user: Annotated[models.User | models.AnonymousUser, Depends(AuthController.get_user_from_token)],
    has_permission: Annotated[bool, Depends(AuthController.get_permission_dependency("post_geofile"))]
):

    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Não possui permissão.")

    extension = os.path.splitext(file.filename)[1]
    fd, file_path = tempfile.mkstemp(prefix='parser_', suffix=extension)

    if extension not in ('.tif', '.tiff'):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Extensão invalida.")

    return await controller.upload_raster(fd, file, file_path, table_name, 4674)


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
