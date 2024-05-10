from os import getenv
from typing import Annotated

from fastapi import BackgroundTasks, Depends, status
from fastapi.exceptions import HTTPException
from passlib.context import CryptContext
from sqlmodel.ext.asyncio.session import AsyncSession

from repositories.user_repository import UserRepository
from schemas.user import UserCreate
from services.email_service import EmailService
from sql_app.database import get_db
from passlib.hash import bcrypt_sha256

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
                password=getenv("PASSWORD_SMTP"),
                background_tasks=background_tasks
            )
        )

    def _hash_password(self, password: str) -> str:
        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        pwd_context.update(bcrypt__salt_size=22)
        print(getenv("SECRET_KEY"))
        return bcrypt_sha256.hash(password+getenv("SECRET_KEY"))

    async def create_temporary_user(self, user: UserCreate):

        user.password = self._hash_password(user.password)
        temporary_user = await self.repository.get_temporary_user_by_email(user.email)
        if temporary_user:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Usuário já cadastrado!")
        user_db = await self.repository.get_user_by_email(user.email)
        if user_db:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Usuário já cadastrado!")

        temporary_user = await self.repository.create_temporary_user(user)

        if getenv('ENVIRONMENT') != 'local' :
            self.background_tasks.add_task(self.email_service.send_account_confirmation_account, to_email=user.email,
                                        ocupation=user.ocupation,
                                        link_url=f"{getenv('HOST_URL')}confirm-email/{temporary_user.id}")

        return temporary_user
