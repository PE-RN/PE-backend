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
from asyncer import syncify
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
            user.ocupation.value
        )

        if getenv('ENVIRONMENT') != 'local':
            self.background_tasks.add_task(
                self._send_email_account_confirmation_wrapper,
                email_message=email_message,
                temporary_user=temporary_user
            )

        return temporary_user

    def _create_confirmation_account_email_message(self, to_email, link_url, ocupation) -> EmailMessage:

        link_url = self._replace_safety_url_for_sender_pattern(link_url)

        content = f'<h3 style="color:#0dace3;"> {ocupation.capitalize()} para confirmar seu email na plataforma por favor click  no link'
        content += f' <a style="display: inline-block;" href="{link_url}">LINK</a> !! <h3>'

        return EmailMessage(html_content=content, subject="Confirmação de email Plataforma Atlas", to_email=to_email)

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
