from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select
from schemas.user import UserCreate
from sql_app import models


class UserRepository:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_temporary_user_by_email(self, email):
        statment = select(models.TemporaryUser).filter_by(email=email).fetch(1)
        temporary_users = await self.db.exec(statment)
        return temporary_users.first()

    async def get_user_by_email(self, email):
        statment = select(models.User).filter_by(email=email).fetch(1)
        users = await self.db.exec(statment)
        return users.first()

    async def create_temporary_user(self, user: UserCreate):
        db_temporary_user = models.TemporaryUser(**user.model_dump(exclude=['ocupation']), ocupation=user.ocupation.value)
        self.db.add(db_temporary_user)
        await self.db.commit()
        await self.db.refresh(db_temporary_user)
        return db_temporary_user

    async def create_user(self, user: UserCreate):
        db_user = models.User(email=user.email, password=user.password, ocupation=user.ocupation.value, group_id=user.group_id)
        self.db.add(db_user)
        await self.db.commit()
        await self.db.refresh(db_user)
        return db_user
