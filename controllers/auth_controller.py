from datetime import datetime, timedelta, timezone
from os import getenv
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, status
from fastapi.exceptions import HTTPException
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import EmailStr
from sqlmodel.ext.asyncio.session import AsyncSession

from repositories.auth_repository import AuthRepository
from schemas.token import Token
from sql_app.database import get_db
from sql_app.models import User
from passlib.hash import bcrypt_sha256


class AuthController:

    def __init__(self, repository: AuthRepository):
        self.repository = repository

    @staticmethod
    def inject_repository(db: Annotated[AsyncSession, Depends(get_db)]) -> AuthRepository:
        return AuthRepository(db=db)

    @staticmethod
    def inject_controller(repository: Annotated[AuthRepository, Depends(inject_repository)]):
        return AuthController(repository=repository)

    @staticmethod
    async def get_user_from_token(
        repository: Annotated[AuthRepository, Depends(inject_repository)],
        authorization: Annotated[str, Header()]
    ) -> User:

        token = authorization.split(' ')[1]
        try:
            payload = jwt.decode(token, getenv("SECRET_KEY"), algorithms=[getenv("ALGORITHM")])
            current_time = datetime.now(timezone.utc)
            expiration_time = payload.get('exp')

            if current_time > datetime.fromtimestamp(expiration_time, timezone.utc):
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expirado!")
            email = payload.get('sub')
            user = await repository.get_user_by_email(email)

            return user

        except JWTError:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido!")

    def verify_password_hash(self, password: str, hashed_password: str) -> bool:
        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        pwd_context.update(bcrypt__salt_size=22)
        return  bcrypt_sha256.verify(password+getenv("SECRET_KEY"), hashed_password)

    def generate_access_token(self, email: str) -> str :
        to_enconde = {"sub": email}
        acess_token_expires_time = datetime.now(timezone.utc) + timedelta(minutes=int(getenv("ACCESS_TOKEN_EXPIRE_MINUTES")))
        to_enconde.update({"exp": acess_token_expires_time})
        return jwt.encode(to_enconde, getenv("SECRET_KEY"), algorithm=getenv("ALGORITHM"))

    async def get_acess_token_user(self, email: EmailStr, password: str) -> Token:
        user = await self.authenticate_user(email, password)
        if not user:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Usuário não encontrado!")
        if not self.verify_password_hash(password, user.password):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Credenciais inválidas!")

        return Token(acess_token=self.generate_access_token(email), token_type="Bearear")

    async def authenticate_user(self, email: EmailStr, password: str) -> User | None:
        user = await self.repository.get_user_by_email(email)
        if user and self.verify_password_hash(password, user.password):
            return user

        return None

    async def confirm_email(self, temporary_user_id: UUID) -> None:
        temporary_user = await self.repository.get_temporary_user_by_id(temporary_user_id)
        if temporary_user:
            user = await self.repository.get_user_by_email(temporary_user.email)
            if user:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Usuário já confirmado!")

            await self.repository.create_user_from_temporary(temporary_user)
            await self.repository.delete_temporary_user(temporary_user)
            return

    async def validate_and_get_email_from_token(self, token: str) -> str:
        payload = jwt.decode(token, getenv("SECRET_KEY"), algorithms=[getenv("ALGORITHM")])
        issued_at = payload.get("iat")
        if not issued_at:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

        current_time = datetime.now(timezone.utc)
        token_age = current_time - datetime.fromtimestamp(issued_at, timezone.utc)

        if token_age.total_seconds() > int(getenv("REFRESH_TOKEN_EXPIRE_MINUTES")) * 60:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token expired")

        email = payload.get("sub")
        if not email:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate credentials")

        user = await self.repository.get_user_by_email(email)
        if not user or not user.is_active:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not find user")

        return email

    async def refresh_tokens(self, token) -> Token:
        email = await self.validate_and_get_email_from_token(token)
        new_access_token = self.generate_access_token(email)
        return Token(access_token=new_access_token,token_type="Bearer")
