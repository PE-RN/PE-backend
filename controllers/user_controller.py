from fastapi import BackgroundTasks
from repositories.user_repository import UserRepository
from schemas.user import UserCreate
from passlib.context import CryptContext
from services.email_service import EmailService

class UserController:

    def __init__(self, repository: UserRepository,email_service:EmailService,background_tasks:BackgroundTasks):
        self.repository = repository
        self.email_service = email_service
        self.background_tasks = background_tasks

    def _hash_password(self, password: str) -> str:
        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        pwd_context.update(bcrypt__salt_size=5)

        return pwd_context.hash(password)

    async def create_temporary_user(self, user: UserCreate):
        user.password = self._hash_password(user.password)
        temporary_user = await self.repository.create_temporary_user(user) 
        self.background_tasks.add_task(self.email_service.send_account_confirmation_account, to_email=user.email, ocupation=user.ocupation,
                                       link_url=f'localhost:8000/confirm-email/{temporary_user.id}' 
                                       )

        return temporary_user
