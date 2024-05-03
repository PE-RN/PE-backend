from sqlalchemy.orm import Session
from sqlmodel.ext.asyncio.session import AsyncSession
from schemas.user import UserCreate
from sql_app.models import User, TemporaryUser


class UserRepository:

    def __init__(self, db: AsyncSession):
        self.db = db

    
    async def create_temporary_user(self, user: UserCreate):
        db_temporary_user = TemporaryUser(**user.model_dump())
        self.db.add(db_temporary_user)
        await self.db.commit()
        await self.db.refresh(db_temporary_user)
        return db_temporary_user

    
    async def create_user(self, user: UserCreate):
        db_user = User(email=user.email, password=user.password, ocupation=user.ocupation, group_id=user.group_id)
        self.db.add(db_user)
        await self.db.commit()
        await self.db.refresh(db_user)
        return db_user
