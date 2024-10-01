from os import getenv
from typing import Annotated

from fastapi import BackgroundTasks, Depends, status
from fastapi.exceptions import HTTPException
from sentry_sdk import capture_exception
from sqlmodel.ext.asyncio.session import AsyncSession

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

    def __init__(self, repository: UserRepository, email_service: EmailService, background_tasks: BackgroundTasks):
        self.repository = repository
        self.email_service = email_service
        self.background_tasks = background_tasks

    @staticmethod
    async def inject_controller(background_tasks: BackgroundTasks, db: Annotated[AsyncSession, Depends(get_db)]):

        return UserController(
            repository=UserRepository(db=db),
            email_service=EmailService(
                host=getenv("SMTP_HOST"),
                port=getenv("SMTP_PORT"),
                email=getenv("EMAIL_SMTP"),
                password=getenv("PASSWORD_SMTP")
            ),
            background_tasks=background_tasks
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

    async def update_user(self, user: User, user_update: dict):

        if 'password' in user_update:
            user_update['password'] = self._hash_password(user_update['password'])

        return await self.repository.update_user(user, user_update)

    async def get_all_users(self):

        return await self.repository.get_all_users()

    async def get_user_by_id(self, id: str):

        return await self.repository.get_user_by_id(id)
