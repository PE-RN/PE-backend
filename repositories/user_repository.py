from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select
from schemas.user import UserCreate
from sql_app import models
import datetime


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

    async def delete_temporary_user(self, temporary_user: models.TemporaryUser):

        await self.db.delete(temporary_user)

    async def create_log_email(self, content: str, to: str, sender: str, subject: str, has_error: bool, error_message: str):

        db_log_email = models.LogsEmail(
            content=content,
            to=to,
            sender=sender,
            subject=subject,
            has_error=has_error,
            error_message=error_message
        )
        self.db.add(db_log_email)
        await self.db.commit()
        return await self.db.refresh(db_log_email)

    async def update_user(self, user: models.User, user_update: dict):

        for key, value in user_update.items():
            if key in ('id', 'created_at', 'group'):
                continue

            if value is None:
                continue

            setattr(user, key, value)

        user.updated_at = datetime.datetime.now()
        await self.db.commit()
        await self.db.refresh(user)

        return user

    async def get_all_users(self):

        statment = select(models.User)
        users = await self.db.exec(statment)
        return users.fetchall()

    async def get_user_by_id(self, id: str):

        statment = select(models.User).filter_by(id=id).fetch(1)

        users = await self.db.exec(statment)
        return users.first()
