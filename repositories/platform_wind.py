from sqlalchemy.dialects.postgresql import insert
from sqlmodel import select,delete
from sqlmodel.ext.asyncio.session import AsyncSession
from sql_app.models import Platform, QualifiedData
from uuid import UUID

from sqlalchemy.orm import selectinload
from sqlalchemy import select, func, or_, and_, true, cast, case, Numeric
from sqlalchemy.dialects.postgresql import JSONB, aggregate_order_by
from datetime import datetime, time
import numpy as np
from datetime import date


class PlatformRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def insert_batch_platform(self, batch: list[dict]):
        await self.db.execute(insert(Platform), batch)

    def insert_platform(self, platform: Platform):
        self.db.add(platform)
    
    async def refresh_platform(self, platform: Platform):
        await self.db.refresh(platform)

    async def get_platform(self, name: str  = None, id: UUID = None) -> Platform | None:
        if name is not None:
            query = select(Platform).where(Platform.name == name)#.options(selectinload(Platform.flag_speed))
        elif id is not None:
            query = select(Platform).where(Platform.id == id)#.options(selectinload(Platform.flag_speed))
        #.options(selectinload(Platform.raw_data))  # <<< CARREGAMENTO AQUI
        
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
        # OU return result.first()


    async def get_data_timeseries_by_height(self, platform, field_name: str, start_search_date, end_search_date, ):
        query = (
            select(
                func.max(QualifiedData.height).label("height"),
                func.json_agg(
                    aggregate_order_by(#Ordenar subgrupo
                        func.json_build_object(
                            f"{field_name}", getattr(QualifiedData, field_name, None),
                            "dt", QualifiedData.dt
                        ),
                    QualifiedData.dt.asc()#ordenar por
                    ),
                ).label("height_levels")
            )
            .where(
                QualifiedData.plat_id == platform["id"],
                QualifiedData.dt >= start_search_date if start_search_date is not None else true,
                QualifiedData.dt <= end_search_date if end_search_date is not None else true,
            )
            .group_by(
                QualifiedData.height,
                QualifiedData.plat_id
            )
            .order_by(QualifiedData.height)#Ordenar principal
        )

        result = await self.db.execute(query)
        return result.all()
    
    async def get_last_date(self, platform_id):
        query = (
            select(func.max(QualifiedData.dt).label("last_date"))
            .where(QualifiedData.plat_id == platform_id)
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_wind_rose_base_data(self, platform, start_search_date, end_search_date, height=None):
        query = (
            select(
                QualifiedData.height,
                QualifiedData.h_spd,
                QualifiedData.wdir,
                QualifiedData.ti,
            )
            .where(
                QualifiedData.plat_id == platform["id"],
                QualifiedData.dt >= start_search_date if start_search_date is not None else True,
                QualifiedData.dt <= end_search_date if end_search_date is not None else True,
                QualifiedData.height == height if height is not None else True,
            )
            .order_by(QualifiedData.dt)
        )

        result = await self.db.execute(query)
        return result.all()

    async def list_all_platforms(self) -> list[Platform] | None:
        query = select(Platform)
        result = await self.db.execute(query)
        platforms = result.scalars().all()
        return [p.model_dump() for p in platforms]

    async def insert_batch_qualified_data(self, batch: list[dict]):
        await self.db.execute(insert(QualifiedData), batch)

    async def getHeightByPlatform(self, platform:Platform, start_datetime=None, end_datetime=None ):
        query = (
            select(QualifiedData.height)
            .where(
                QualifiedData.plat_id == platform["id"],
                QualifiedData.dt >= start_datetime if start_datetime is not None else true,
                QualifiedData.dt <= end_datetime if end_datetime is not None else true,
                )
            .group_by(QualifiedData.height)
            .order_by(QualifiedData.height)
        )
        result = await self.db.execute(query)
        rows = result.scalars().all()
        return rows


    async def get_hourly_mean_over_days(self, platform, field_name: str, start_dt, end_dt):
        avg_expr = self.create_avg_expr(field_name)        
        #Extraindo a hora do datetime
        hour = func.extract("hour", QualifiedData.dt).label("hour")#EXTRACT(HOUR FROM dt) AS hour
        query = (
            select(
                QualifiedData.height,
                hour,
                avg_expr.label("avg"),
                # func.avg(getattr(QualifiedData, field_name)).label("avg_value")#Calcula a média dos valores dessa coluna.
            )
            .where(
                QualifiedData.plat_id == platform["id"],
                QualifiedData.dt >= start_dt if start_dt is not None else true,
                QualifiedData.dt <= end_dt if end_dt is not None else true,
                getattr(QualifiedData, field_name) != np.nan,
            )
            .group_by(QualifiedData.height,hour)
            .order_by(QualifiedData.height,hour)
        )
        result = await self.db.execute(query)
        return result.all()
    
    async def get_average_by_height(self, platform, field_name: str, start_search_date, end_search_date):
        avg_expr = self.create_avg_expr(field_name)

        query = (
            select(
                QualifiedData.height,
                avg_expr.label("avg")
            )
            .where(
                QualifiedData.plat_id == platform["id"],
                QualifiedData.dt >= start_search_date if start_search_date is not None else true,
                QualifiedData.dt <= end_search_date if end_search_date is not None else true,
                getattr(QualifiedData, field_name) != np.nan,
            )
            .group_by(QualifiedData.height)
            .order_by(QualifiedData.height)
        )
        result = await self.db.execute(query)
        return result.all()

    def create_avg_expr(self, field_name):
        if field_name == "wdir" or field_name == "m_wdir":
            return self.func_avg_dir(QualifiedData, field_name)
        else:
            avg_expr = func.avg(getattr(QualifiedData, field_name))#Media simples de field_name
        return avg_expr
    
    def func_avg_dir(self, DataModel, field_name):
        """
            Converte graus em radianos
            Calcula seno e cosseno, Faz a média, Usa atan2, Converte de volta para graus e Normaliza para 0-360
        """
        angle_deg = (
            func.degrees(#Converter de radianos para graus
                func.atan2(#Reconstruir o ângulo (em radianos)
                    func.avg(func.sin(func.radians(getattr(DataModel, field_name)))),#eixo Y → sin(θ) e depois media dos vetores
                    func.avg(func.cos(func.radians(getattr(DataModel, field_name))))#eixo X → cos(θ) e depois media dos vetores
                )
            ) + 360 #Garantir valor positivo (De -180 ate +180 para +180 ate +540)
        )
        avg_expr = func.mod(# Intervalo de 0 a 360
            cast(angle_deg, Numeric),#Necessario fazer cast para usar o modulo, PostgreSQL não aceita mod(double precision, integer)
            360
        )
        return avg_expr
    
    async def delete_qualified_data_between_datetimes(self, platform, start_datetime, end_datetime):        
        statement = delete(QualifiedData).where(
            QualifiedData.plat_id == platform["id"],
            QualifiedData.dt >= start_datetime,
            QualifiedData.dt <= end_datetime
        )
        await self.db.exec(statement)
        return await self.db.commit()
    
    async def commit(self):
        await self.db.commit()
    

    async def rollback(self):
        await self.db.rollback()