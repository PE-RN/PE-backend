from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.orm import selectinload

from sql_app import models


class AuthRepository:

    def __init__(self, db: AsyncSession):

        self.db = db

    async def create_user_from_temporary(self, temporary_user: models.TemporaryUser):

        user = models.User(**temporary_user.model_dump(exclude_defaults=True))
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def delete_temporary_user(self, temporary_user: models.TemporaryUser):

        await self.db.delete(temporary_user)
        await self.db.commit()

    async def get_user_by_email(self, email: str):

        statement = select(models.User).filter_by(email=email).fetch(1)
        users = await self.db.exec(statement)
        return users.first()

    async def get_temporary_user_by_email(self, email: str):

        statement = select(models.TemporaryUser).filter_by(email=email).fetch(1)
        users = await self.db.exec(statement)
        return users.first()

    async def create_log_email(self, content: str, to: str, sender: str, subject: str, has_error: bool, error_message: str | None = None):

        log_email = models.LogsEmail(content=content, to=to, sender=sender, subject=subject, has_error=has_error, error_message=error_message)
        self.db.add(log_email)
        await self.db.commit()
        return await self.db.refresh(log_email)

    async def get_temporary_user_by_id(self, temporary_user_id):

        statement = select(models.TemporaryUser).filter_by(id=temporary_user_id).fetch(1)
        users = await self.db.exec(statement)
        return users.first()

    async def update_user(self, user: models.User):

        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def create_anonymous_user(self, ocupation: str) -> models.AnonymousUser:

        db_anonymous_user = models.AnonymousUser(ocupation=ocupation)
        self.db.add(db_anonymous_user)
        await self.db.commit()
        await self.db.refresh(db_anonymous_user)
        return db_anonymous_user

    async def get_anonymous_user_by_id(self, anonymous_user_id) -> models.AnonymousUser | None:

        statement = select(models.AnonymousUser).filter_by(id=anonymous_user_id).fetch(1)
        anonymous_users = await self.db.exec(statement)
        return anonymous_users.first()

    async def check_permission(self, user: models.User, permission_name: str) -> bool:
        query = (
            select(models.User)
            .options(selectinload(models.User.group).selectinload(models.Group.permissions))
            .where(models.User.id == user.id)
        )
        result = await self.db.exec(query)
        user_with_group = result.first()

        if user_with_group and user_with_group.group:
            for permission in user_with_group.group.permissions:
                if permission.name == permission_name:
                    return True
        return False
