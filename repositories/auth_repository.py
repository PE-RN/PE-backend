from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import and_, func
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.orm import selectinload

from enums.group_enum import GroupNameEnum
from sql_app import models

class AuthRepository:

    def __init__(self, db: AsyncSession):

        self.db = db

    async def create_user_from_temporary(
        self,
        temporary_user: models.TemporaryUser,
        group_id: UUID | None = None,
    ):

        user_payload = temporary_user.model_dump(exclude_defaults=True)
        if group_id is not None:
            user_payload["group_id"] = group_id

        user = models.User(**user_payload)
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def get_group_by_name(self, group_name: str) -> models.Group | None:

        statement = select(models.Group).where(
            func.lower(models.Group.name) == group_name.lower()
        ).fetch(1)
        groups = await self.db.exec(statement)
        return groups.first()

    async def get_authenticated_group(self) -> models.Group | None:

        return await self.get_group_by_name(GroupNameEnum.AUTHENTICATED.value)

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

    async def get_user_by_id(self, user_id: UUID) -> models.User | None:

        statement = select(models.User).filter_by(id=user_id).fetch(1)
        result = await self.db.exec(statement)
        return result.first()

    async def create_password_reset_token(
        self, user_id: UUID, token_hash: str, expires_at: datetime
    ) -> models.PasswordResetToken:

        token = models.PasswordResetToken(
            user_id=user_id, token_hash=token_hash, expires_at=expires_at
        )
        self.db.add(token)
        await self.db.commit()
        await self.db.refresh(token)
        return token

    async def get_valid_password_reset_token(
        self, token_hash: str
    ) -> models.PasswordResetToken | None:

        now = datetime.now(timezone.utc)
        statement = select(models.PasswordResetToken).where(
            and_(
                models.PasswordResetToken.token_hash == token_hash,
                models.PasswordResetToken.used == False,
                models.PasswordResetToken.expires_at > now,
            )
        ).fetch(1)
        result = await self.db.exec(statement)
        return result.first()

    async def mark_password_reset_token_used(
        self, token: models.PasswordResetToken
    ) -> None:

        token.used = True
        self.db.add(token)
        await self.db.commit()

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

    async def check_group(self, user: models.User, group_name: str) -> bool:
        query = (
            select(models.User)
            .options(selectinload(models.User.group))
            .where(models.User.id == user.id)
        )
        result = await self.db.exec(query)
        user_with_group = result.first()

        if user_with_group and user_with_group.group:
            if user_with_group.group.name == group_name:
                return True
        return False
