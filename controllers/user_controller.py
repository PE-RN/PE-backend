from os import getenv
from typing import Annotated

from fastapi import BackgroundTasks, Depends, status
from fastapi.exceptions import HTTPException
from sentry_sdk import capture_exception
from sqlmodel.ext.asyncio.session import AsyncSession

from controllers.auth_controller import AuthController
from repositories.user_repository import UserRepository
from schemas.user import UserCreate
from schemas.email import EmailMessage
from services.email_service import EmailService
from sql_app.database import get_db
from sql_app.models import TemporaryUser
from sql_app.models import User
from asyncer import syncify
from utils.html_generator import HtmlGenerator
import bcrypt


class UserController:

    def __init__(self, repository: UserRepository, email_service: EmailService, background_tasks: BackgroundTasks, auth_controller: AuthController):
        self.repository = repository
        self.email_service = email_service
        self.background_tasks = background_tasks
        self.auth_controller = auth_controller

    @staticmethod
    async def inject_controller(background_tasks: BackgroundTasks, db: Annotated[AsyncSession, Depends(get_db)]):

        auth_controller = AuthController.inject_controller(background_tasks, db)

        return UserController(
            repository=UserRepository(db=db),
            email_service=EmailService(
                host=getenv("SMTP_HOST"),
                port=getenv("SMTP_PORT"),
                email=getenv("EMAIL_SMTP"),
                password=getenv("PASSWORD_SMTP")
            ),
            background_tasks=background_tasks,
            auth_controller=auth_controller
        )

    def _replace_safety_url_for_sender_pattern(self, url: str) -> str:
        return url.replace("&", "&amp;").replace("?", "&quest;")

    def _hash_password(self, password: str) -> str:

        bytes_pass = password.encode('utf-8')
        salt = bcrypt.gensalt()
        hash = bcrypt.hashpw(bytes_pass, salt)

        return hash.decode('utf-8')

    async def create_temporary_user(self, user: UserCreate):

        user.password = self._hash_password(user.password)
        temporary_user = await self.repository.get_temporary_user_by_email(user.email)
        if temporary_user:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Usuário já cadastrado!")
        user_db = await self.repository.get_user_by_email(user.email)
        if user_db:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Usuário já cadastrado!")

        temporary_user = await self.repository.create_temporary_user(user)
        email_message = self._create_confirmation_account_email_message(
            user.email,
            f"{getenv('HOST_URL')}confirm-email/{temporary_user.id}",
        )

        if getenv('ENVIRONMENT') != 'local':
            self.background_tasks.add_task(
                self._send_email_account_confirmation_wrapper,
                email_message=email_message,
                temporary_user=temporary_user
            )

        return temporary_user

    def _create_confirmation_account_email_message(self, to_email, confirmation_link_url) -> EmailMessage:

        link_url = self._replace_safety_url_for_sender_pattern(confirmation_link_url)

        content = HtmlGenerator().confirmation_account(
            img_logo_cid='logo',
            img_isi_er_cid="isi",
            img_state_cid="estado",
            user_email=to_email,
            contact_link=f"{getenv('FRONT_URL')}pages/contact/contact.html",
            confirmation_email_link=link_url)

        return EmailMessage.with_default_logo_images(html_content=content, subject="Confirmação de email Plataforma de Energias do RN", to_email=to_email)

    def _send_email_account_confirmation_wrapper(self, email_message: EmailMessage, temporary_user: TemporaryUser):

        try:
            self.email_service.send_email_account_confirmation(email_message)
            syncify(async_function=self.repository.create_log_email)(
                subject=email_message.subject,
                content=email_message.html_content,
                to=email_message.to_email,
                sender=getenv('EMAIL_SMTP'),
                has_error=False,
                error_message=None
            )
        except Exception as e:
            capture_exception(e)
            syncify(async_function=self.repository.create_log_email)(
                subject=email_message.subject,
                content=email_message.html_content,
                to=email_message.to_email,
                sender=getenv('EMAIL_SMTP'),
                has_error=True,
                error_message=str(e)
            )

    async def update_user(self, user_update: dict, user: User = None, id: str = None):

        if 'current_password' in user_update and 'new_password' in user_update:

            if user_update['current_password'] is not None and user_update['new_password'] is None:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Informe a nova senha")

            if user_update['new_password'] is not None and user_update['current_password'] is None:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Informe a senha atual")

            if user_update['new_password'] is not None and user_update['current_password'] is not None:
                if not self.auth_controller.verify_password_hash(user_update['current_password'], user.password):
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Senha atual incorreta, verifique e tente novamente")

                user_update['password'] = self._hash_password(user_update['new_password'])

            user_update.pop('new_password')
            user_update.pop('current_password')

        if not id:
            return await self.repository.update_user_self(user, user_update)

        return await self.repository.update_user(id, user_update)

    async def get_all_users(self):

        return await self.repository.get_all_users()

    async def get_user_by_id(self, id: str):

        return await self.repository.get_user_by_id(id)

    async def create_permission(self, permission: dict):

        if 'description' not in permission:
            permission['description'] = ''

        return await self.repository.create_permission(permission)

    async def create_group(self, group: dict):

        if 'description' not in group:
            group['description'] = ''

        return await self.repository.create_group(group)

    async def add_permissions_to_group(self, group_id: str, permissions_names: list):

        group = await self.repository.get_group(group_id)

        if not group:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Grupo não encontrado")

        permissions = await self.repository.get_permissions_by_names(permissions_names)

        if len(permissions) == 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Permissões não encontradas")

        for permission in permissions:
            if permission not in group.permissions:
                group.permissions.append(permission)

        await self.repository.update_permissions_to_group(group)

        return group

    async def remove_permissions_to_group(self, group_id: str, permissions_names: list):

        group = await self.repository.get_group(group_id)

        if not group:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Grupo não encontrado")

        if len(group.permissions) == 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="O grupo não possui permissões para serem removidas")

        permissions = await self.repository.get_permissions_by_names(permissions_names)

        if len(permissions) == 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Permissões não encontradas")

        for permission in permissions:
            if permission in group.permissions:
                group.permissions.remove(permission)

        await self.repository.update_permissions_to_group(group)

        return group
