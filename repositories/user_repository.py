from datetime import datetime, timedelta
from sqlalchemy.orm import joinedload
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select, func, case
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

    async def update_user_self(self, user: models.User, user_update: dict):

        for key, value in user_update.items():
            if key in ('id', 'created_at', 'group'):
                continue

            if value is None:
                continue

            setattr(user, key, value)

        user.updated_at = datetime.now()
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

    async def update_user(self, id: str, user_update: dict):

        user = await self.get_user_by_id(id)

        for key, value in user_update.items():
            if key in ('id', 'created_at', 'group'):
                continue

            if value is None:
                continue

            setattr(user, key, value)

        user.updated_at = datetime.now()
        await self.db.commit()
        await self.db.refresh(user)

        return user

    async def create_permission(self, permission: dict):

        new_permission = models.Permission(
            name=permission['name'],
            description=permission['description']
        )

        self.db.add(new_permission)
        await self.db.commit()
        await self.db.refresh(new_permission)
        return new_permission

    async def create_group(self, group: dict):

        new_group = models.Group(
            name=group['name'],
            description=group['description']
        )

        self.db.add(new_group)
        await self.db.commit()
        await self.db.refresh(new_group)
        return new_group

    async def get_group(self, group_id: str):

        statment = select(models.Group).options(joinedload(models.Group.permissions)).filter_by(id=group_id)
        group = await self.db.exec(statment)
        return group.first()

    async def get_permissions_by_names(self, permissions_names: list):

        statment = select(models.Permission).where(models.Permission.name.in_(permissions_names))
        users = await self.db.exec(statment)
        return users.fetchall()

    async def update_permissions_to_group(self, group: models.Group):

        await self.db.commit()
        await self.db.refresh(group)

        return group

    async def get_user_dashboard_data(self):

        now = datetime.now()
        last_month = now - timedelta(days=30)
        last_week = now - timedelta(days=7)

        statement = select(
            func.count(models.User.id).label("total_users"),
            func.sum(case((models.User.created_at >= last_month, 1), else_=0)).label("users_last_month"),
            func.sum(case((models.User.created_at >= last_week, 1), else_=0)).label("users_last_week")
        )
        result = await self.db.exec(statement)
        row = result.first()

        return {
            "total_usuarios": row.total_users,
            "usuarios_ultimo_mes": row.users_last_month,
            "usuarios_ultima_semana": row.users_last_week
        }
