import secrets
import string
from datetime import datetime, timedelta, timezone
from os import getenv
from typing import Annotated, Callable
from uuid import UUID

import bcrypt
from fastapi import BackgroundTasks, Depends, Header, status
from fastapi.exceptions import HTTPException
from fastapi.responses import RedirectResponse
from jose import JWTError, jwt, ExpiredSignatureError
from pydantic import EmailStr
from sentry_sdk import capture_exception
from sqlmodel.ext.asyncio.session import AsyncSession

from repositories.auth_repository import AuthRepository
from schemas.token import Token
from schemas.email import EmailMessage
from services.email_service import EmailService
from sql_app.database import get_db
from sql_app.models import User
from sql_app.models import TemporaryUser
from asyncer import syncify
from utils.html_generator import HtmlGenerator


class AuthController:

    def __init__(self, repository: AuthRepository, email_service: EmailService, background_tasks: BackgroundTasks):

        self.repository = repository
        self.email_service = email_service
        self.background_tasks = background_tasks

    @staticmethod
    def inject_repository(db: Annotated[AsyncSession, Depends(get_db)]) -> AuthRepository:

        return AuthRepository(db=db)

    @staticmethod
    def inject_controller(repository: Annotated[AuthRepository, Depends(inject_repository)], background_tasks: BackgroundTasks):

        return AuthController(repository=repository,
                              background_tasks=background_tasks,
                              email_service=EmailService(
                                  host=getenv('SMTP_HOST'),
                                  port=getenv('SMTP_PORT'),
                                  email=getenv('EMAIL_SMTP'),
                                  password=getenv('PASSWORD_SMTP')))

    @staticmethod
    async def get_user_from_token(
        repository: Annotated[AuthRepository, Depends(inject_repository)],
        authorization: Annotated[str, Header()]
    ) -> User:

        try:
            token_type, token = authorization.split(' ')

            if token_type != getenv('TOKEN_TYPE'):
                raise JWTError
            payload = jwt.decode(token, getenv("SECRET_KEY"), algorithms=[getenv("ALGORITHM")])
            sub = payload.get('sub')
            if not sub:
                raise JWTError

            try:
                anonymous_user = await repository.get_anonymous_user_by_id(sub)
                if anonymous_user:
                    return anonymous_user
            except Exception as e:
                capture_exception(e)
                pass

            email = sub
            user = await repository.get_user_by_email(email)
            return user

        except ExpiredSignatureError:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expirado!")
        except (JWTError, ValueError):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido!")

    def verify_password_hash(self, password: str, hashed_password: str) -> bool:

        try:
            return bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8'))
        except ValueError:
            return False

    def generate_access_token(self, email: str) -> str:

        to_enconde = {"sub": email}
        acess_token_expires_time = datetime.now(timezone.utc) + timedelta(minutes=int(getenv("ACCESS_TOKEN_EXPIRE_MINUTES")))
        to_enconde.update({"exp": acess_token_expires_time})

        return jwt.encode(to_enconde, getenv("SECRET_KEY"), algorithm=getenv("ALGORITHM"))

    def generate_refresh_token(self, email: str) -> str:

        to_enconde = {"sub": email}
        acess_token_expires_time = datetime.now(timezone.utc) + timedelta(minutes=int(getenv("REFRESH_TOKEN_EXPIRE_MINUTES")))
        to_enconde.update({"exp": acess_token_expires_time})

        return jwt.encode(to_enconde, getenv("SECRET_KEY"), algorithm=getenv("ALGORITHM"))

    async def get_token_user(self, email: EmailStr, password: str):

        user = await self.authenticate_user(email, password)
        if not user:
            temporary_user = await self.repository.get_temporary_user_by_email(email)

            if temporary_user:
                email_message = self._create_confirmation_account_email_message(
                    temporary_user.email,
                    f"{getenv('HOST_URL')}confirm-email/{temporary_user.id}",
                )

                self.background_tasks.add_task(
                    self._send_email_account_confirmation_wrapper,
                    email_message=email_message,
                    temporary_user=temporary_user
                )
                return 'resend_email'

            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado!")
        
        is_admin = await self.user_is_admin(repository=self.repository, user=user)

        return Token(access_token=self.generate_access_token(email), refresh_token=self.generate_refresh_token(email), is_admin=is_admin)

    async def authenticate_user(self, email: EmailStr, password: str) -> User | None:

        user = await self.repository.get_user_by_email(email)
        if user:
            if not self.verify_password_hash(password, user.password):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Senha incorreta!")

            return user

        return None

    async def confirm_email(self, temporary_user_id: UUID) -> None:
        temporary_user = await self.repository.get_temporary_user_by_id(temporary_user_id)
        if not temporary_user:
            # Redirect with an error message if the user is not a temporary user
            return RedirectResponse(
                url=f"{getenv('FRONT_URL')}pages/login/login.html?error=Usuário não encontrado!",
                status_code=status.HTTP_302_FOUND
            )

        user = await self.repository.get_user_by_email(temporary_user.email)
        if user:
            # User already exists, raise an exception or handle as needed
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Usuário já confirmado!")

        # Proceed to create user from temporary and delete temporary record
        await self.repository.create_user_from_temporary(temporary_user)
        await self.repository.delete_temporary_user(temporary_user)

        # Redirect to login page normally
        return RedirectResponse(url=f"{getenv('FRONT_URL')}pages/login/login.html?alert=Cadastro confirmado!!", status_code=status.HTTP_302_FOUND)

    async def validate_and_get_email_from_refresh_token(self, token: str) -> str:

        try:
            payload = jwt.decode(token, getenv("SECRET_KEY"), algorithms=[getenv("ALGORITHM")])
        except ExpiredSignatureError:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expirado!")
        except JWTError:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido!")

        # anonymouns user return id
        sub = payload.get('sub')
        try:
            anonymouns = await self.repository.get_anonymous_user_by_id(sub)
            if anonymouns:
                return anonymouns.id.hex
        except Exception as e:
            capture_exception(e)
            pass

        email = payload.get("sub")
        if not email:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Não foi possível validar as credencias!")

        user = await self.repository.get_user_by_email(email)
        if not user or not user.is_active:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuário não encontrado!")

        return email

    async def refresh_tokens(self, token) -> Token:

        email = await self.validate_and_get_email_from_refresh_token(token)
        new_access_token = self.generate_access_token(email)
        new_refresh_token = self.generate_refresh_token(email)
        return Token(access_token=new_access_token, refresh_token=new_refresh_token)

    def generate_temporary_password(self):

        caracteres = string.digits
        senha = ''.join(secrets.choice(caracteres) for _ in range(9))
        return senha

    def _hash_password(self, password: str) -> str:

        bytes_pass = password.encode('utf-8')
        salt = bcrypt.gensalt()
        hash = bcrypt.hashpw(bytes_pass, salt)

        return hash.decode('utf-8')

    async def recovery_password(self, user_email: str) -> None:

        user = await self.repository.get_user_by_email(user_email)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado!")

        temporary_password = self.generate_temporary_password()
        temporary_password_hashed = self._hash_password(temporary_password)

        user.password = temporary_password_hashed
        await self.repository.update_user(user)
        email_message = self._create_recovery_email_message(temporary_password, user.email)

        self.background_tasks.add_task(self._send_email_recovery_password_wrapper, email_message=email_message)

    async def change_password(self, user: User, actual_password: str, new_password: str) -> None:

        if not self.verify_password_hash(actual_password, user.password):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Senha atual incorreta!")

        new_password_hashed = self._hash_password(new_password)
        user.password = new_password_hashed
        await self.repository.update_user(user)

    async def create_anonymous_user(self, ocupation: str):

        anonymous_user = await self.repository.create_anonymous_user(ocupation=ocupation)
        # Passing ID to hash againts email beccause is anonymouns
        access_token = self.generate_access_token(email=anonymous_user.id.hex)
        refresh_token = self.generate_refresh_token(email=anonymous_user.id.hex)

        return Token(access_token=access_token, refresh_token=refresh_token)

    def _create_recovery_email_message(self, new_password, to_email) -> EmailMessage:

        content = HtmlGenerator().get_password_recovery(
            contact_link=f"{getenv('FRONT_URL')}pages/contact/contact.html",
            user_email=to_email,
            enter_link=f"{getenv('FRONT_URL')}pages/login/login.html",
            img_logo_cid='logo',
            reset_password_link=f"{getenv('FRONT_URL')}pages/login/login.html",  # TODO moved to correct page after the page is ready on front side
            img_isi_er_cid='isi',
            img_state_cid='estado',
            new_password=new_password)

        return EmailMessage.with_default_logo_images(to_email=to_email, subject="Recuperação de senha Plataforma de Energias do RN", html_content=content)

    def _send_email_recovery_password_wrapper(self, email_message: EmailMessage):
        try:
            self.email_service.send_email_recovery_password(email_message)
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

    def _replace_safety_url_for_sender_pattern(self, url: str) -> str:
        return url.replace("&", "&amp;").replace("?", "&quest;")

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


    @staticmethod
    def get_permission_dependency(permission_name: str) -> Callable[..., bool]:
        @staticmethod
        def inject_repository(db: Annotated[AsyncSession, Depends(get_db)]) -> AuthRepository:

            return AuthRepository(db=db)

        async def permission_dependency(
            repository: Annotated[AuthRepository, Depends(inject_repository)],
            user: User = Depends(AuthController.get_user_from_token)
        ) -> bool:
            return await AuthController.user_has_permission(permission_name, repository, user)

        return permission_dependency

    @staticmethod
    async def user_has_permission(
        permission_name: str,
        repository: AuthRepository,
        user: User
    ) -> bool:
        return await repository.check_permission(user, permission_name)
    
    @staticmethod
    async def user_is_admin(
        repository: AuthRepository,
        user: User,
        group_name: str = "admin" 
    ) -> bool:
        """
        Check if the user is an admin.
        """
        return await repository.check_group(user, group_name)
