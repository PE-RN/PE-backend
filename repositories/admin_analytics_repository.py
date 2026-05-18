from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import selectinload
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from sql_app import models


class AdminAnalyticsRepository:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_users(self) -> list[models.User]:
        statement = (
            select(models.User)
            .options(selectinload(models.User.group))
            .where(models.User.deleted_at.is_(None))
        )
        result = await self.db.exec(statement)
        return list(result.all())

    async def list_files(self) -> list[models.PdfFile]:
        statement = select(models.PdfFile).where(models.PdfFile.deleted_at.is_(None))
        result = await self.db.exec(statement)
        return list(result.all())

    async def list_layers(self) -> list[models.Layer]:
        statement = select(models.Layer).where(models.Layer.deleted_at.is_(None))
        result = await self.db.exec(statement)
        return list(result.all())

    async def list_layer_groups(self) -> list[models.LayerGroups]:
        statement = select(models.LayerGroups).where(models.LayerGroups.deleted_at.is_(None))
        result = await self.db.exec(statement)
        return list(result.all())

    async def list_events(self) -> list[models.AdminAnalyticsEvent]:
        statement = select(models.AdminAnalyticsEvent).where(models.AdminAnalyticsEvent.deleted_at.is_(None))
        result = await self.db.exec(statement)
        return list(result.all())

    async def get_user_by_id(self, user_id: str) -> models.User | None:
        parsed_id = self._parse_uuid(user_id)
        if parsed_id is None:
            return None

        statement = (
            select(models.User)
            .options(selectinload(models.User.group))
            .where(models.User.id == parsed_id)
            .where(models.User.deleted_at.is_(None))
        )
        result = await self.db.exec(statement)
        return result.first()

    async def get_file_by_id(self, file_id: str) -> models.PdfFile | None:
        parsed_id = self._parse_uuid(file_id)
        if parsed_id is None:
            return None

        statement = (
            select(models.PdfFile)
            .where(models.PdfFile.id == parsed_id)
            .where(models.PdfFile.deleted_at.is_(None))
        )
        result = await self.db.exec(statement)
        return result.first()

    async def get_layer_by_id(self, layer_id: str) -> models.Layer | None:
        parsed_id = self._parse_uuid(layer_id)
        if parsed_id is None:
            return None

        statement = (
            select(models.Layer)
            .where(models.Layer.id == parsed_id)
            .where(models.Layer.deleted_at.is_(None))
        )
        result = await self.db.exec(statement)
        return result.first()

    async def get_event_by_id(self, event_id: str) -> models.AdminAnalyticsEvent | None:
        parsed_id = self._parse_uuid(event_id)
        if parsed_id is None:
            return None

        statement = (
            select(models.AdminAnalyticsEvent)
            .where(models.AdminAnalyticsEvent.id == parsed_id)
            .where(models.AdminAnalyticsEvent.deleted_at.is_(None))
        )
        result = await self.db.exec(statement)
        return result.first()

    async def create_event(
        self,
        domain: str,
        event_type: str,
        label: str,
        occurred_at: datetime,
        *,
        actor_user_id: UUID | None = None,
        actor_name: str | None = None,
        target_type: str | None = None,
        target_id: str | None = None,
        status: str | None = None,
        endpoint_key: str | None = None,
        method: str | None = None,
        status_code: int | None = None,
        latency_ms: int | None = None,
        file_id: UUID | None = None,
        layer_id: UUID | None = None,
        payload: dict[str, object] | None = None,
    ) -> models.AdminAnalyticsEvent:
        db_event = models.AdminAnalyticsEvent(
            domain=domain,
            event_type=event_type,
            label=label,
            occurred_at=occurred_at,
            actor_user_id=actor_user_id,
            actor_name=actor_name,
            target_type=target_type,
            target_id=target_id,
            status=status,
            endpoint_key=endpoint_key,
            method=method,
            status_code=status_code,
            latency_ms=latency_ms,
            file_id=file_id,
            layer_id=layer_id,
            payload=payload,
        )
        self.db.add(db_event)
        await self.db.commit()
        await self.db.refresh(db_event)
        return db_event

    async def create_export(
        self,
        domain: str,
        format_name: str,
        status: str,
        name: str,
        path: str,
        content_type: str,
        generated_at: datetime | None,
        expires_at: datetime | None,
        detail: str | None,
        filters: dict[str, object] | None,
        columns: list[str] | None,
    ) -> models.AdminAnalyticsExport:
        db_export = models.AdminAnalyticsExport(
            domain=domain,
            format=format_name,
            status=status,
            name=name,
            path=path,
            content_type=content_type,
            generated_at=generated_at,
            expires_at=expires_at,
            detail=detail,
            filters=filters,
            columns=columns,
        )
        self.db.add(db_export)
        await self.db.commit()
        await self.db.refresh(db_export)
        return db_export

    async def get_export_by_id(self, export_id: str) -> models.AdminAnalyticsExport | None:
        parsed_id = self._parse_uuid(export_id)
        if parsed_id is None:
            return None

        statement = (
            select(models.AdminAnalyticsExport)
            .where(models.AdminAnalyticsExport.id == parsed_id)
            .where(models.AdminAnalyticsExport.deleted_at.is_(None))
        )
        result = await self.db.exec(statement)
        return result.first()

    @staticmethod
    def _parse_uuid(value: str) -> UUID | None:
        try:
            return UUID(str(value))
        except (TypeError, ValueError):
            return None