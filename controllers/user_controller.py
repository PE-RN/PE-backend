from repositories.user_repository import UserRepository
from schemas.user import UserCreate


class UserController:

    def __init__(self, repository: UserRepository):
        self.repository = repository

    def create_user(self, user: UserCreate):
        self.repository.create_user(user)
