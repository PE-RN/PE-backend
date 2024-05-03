from schemas.token import Token
from datetime import timedelta, datetime, timezone
from pydantic import EmailStr
from repositories.auth_repository import AuthRepository
from passlib.context import CryptContext
from fastapi.exceptions import HTTPException
from fastapi import status
from jose import JWTError, jwt
from uuid import UUID

class AuthController:

    SECRET_KEY = "00e6c33aa1a2d3da5fa7766aae8b1dfc5293341f7104a92097a5e26b09640059"
    ALGORITHM = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES = 60
    REFRESH_TOKEN_EXPIRE_MINUTES = 24*60
    
    
    def __init__(self, repository: AuthRepository):
        self.repository = repository

    def verify_password_hash(self,password,hashed_password):
        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        pwd_context.update(bcrypt__salt_size=5)
        
        return pwd_context.verify(password,hashed_password)
    
    def generate_acess_token(self,email):
        to_enconde = {"sub": email}
        acess_token_expires_time  =  datetime.now(timezone.utc) + timedelta(minutes=AuthController.ACCESS_TOKEN_EXPIRE_MINUTES)
        to_enconde.update({"exp": acess_token_expires_time})
        return jwt.encode(to_enconde, AuthController.SECRET_KEY, algorithm=AuthController.ALGORITHM)         


    async def get_acess_token_user(self,email:EmailStr, password: str):
        user = await self.authenticate_user(email, password)
        if not user:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Usuário não encontrado!")
        if not self.verify_password_hash(password,user.password):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Credenciais inválidas!")
        
        
        return  {"acess_token": self.generate_acess_token(email), "token_type":"Bearear"}                    
    
    async def authenticate_user(self,email: EmailStr, password: str):
        user = await self.repository.get_user_by_email(email)
        if user and self.verify_password_hash(password, user.password):
            return user
        
        return None

    async def confirm_email(self, temporary_user_id: UUID):
        temporary_user = await self.repository.get_temporary_user_by_id(temporary_user_id)
        if temporary_user:
            await self.repository.create_user_and_delete_temporary(temporary_user)
            return
    
    async def validate_and_get_email_from_token(self, token) -> str:
        payload = jwt.decode(token, AuthController.SECRET_KEY, algorithms=[AuthController.ALGORITHM])
        issued_at = payload.get("iat")
        if not issued_at:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
        
        current_time = datetime.now(timezone.utc)
        token_age = current_time - datetime.fromtimestamp(issued_at,timezone.utc)

        if token_age.total_seconds() > AuthController.REFRESH_TOKEN_EXPIRE_MINUTES * 60:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token expired")
        
        email = payload.get("sub")
        if not email:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate credentials")
        
        user = await self.repository.get_user_by_email(email)
        if not user or not user.is_active:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not find user")
        
        return email

    
    async def refresh_tokens(self, token):
        email = await self.validate_and_get_email_from_token(token)         
        new_access_token = self.generate_access_token(email)
        return {"access_token": new_access_token, "token_type": "Bearer"}
            
        

        