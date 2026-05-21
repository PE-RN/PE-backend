from uuid import UUID

import numpy as np
from sqlalchemy import Numeric, cast, func, select, true
from sqlalchemy.dialects.postgresql import aggregate_order_by, insert
from sqlalchemy.orm import selectinload
from sqlmodel import delete
from sqlmodel.ext.asyncio.session import AsyncSession

from sql_app.models import DataStation, LidarStationData, SolarimetricStationData, StationType


class PlatformRepository:
    def __init__(self, db: AsyncSession):
        self.db = db


    def insert_platform(self, station: DataStation):
        self.db.add(station)
    

    async def refresh_platform(self, station: DataStation):
        await self.db.refresh(station)


    async def get_station_type(self, station_type_id: UUID) -> StationType | None:
        query = select(StationType).where(StationType.id == station_type_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()


    async def get_platform(
        self,
        name: str | None = None,
        id: UUID | None = None,
        layer_id: UUID | None = None,
        station_type: UUID | None = None,
    ) -> DataStation | None:
        query = select(DataStation).options(selectinload(DataStation.station_type_ref))
        if name is not None:
            query = query.where(DataStation.name == name)
        if id is not None:
            query = query.where(DataStation.id == id)
        if layer_id is not None:
            query = query.where(DataStation.layer_id == layer_id)
        if station_type is not None:
            query = query.where(DataStation.type == station_type)

        result = await self.db.execute(query.limit(1))
        return result.scalar_one_or_none()


    async def list_all_platforms(
        self,
        name: str | None = None,
        layer_id: UUID | None = None,
        station_type: UUID | None = None,
    ) -> list[DataStation]:
        query = select(DataStation).options(selectinload(DataStation.station_type_ref))
        if name is not None:
            query = query.where(DataStation.name == name)
        if layer_id is not None:
            query = query.where(DataStation.layer_id == layer_id)
        if station_type is not None:
            query = query.where(DataStation.type == station_type)

        result = await self.db.execute(query.order_by(DataStation.name))
        return list(result.scalars().all())


    async def get_data_timeseries(self, station: DataStation, data_model, field_name: str, start_search_date, end_search_date):
        field_column = getattr(data_model, field_name)
        query = (
            select(
                data_model.dt.label("dt"),
                field_column.label("value"),
            )
            .where(
                data_model.station_id == station.id,
                data_model.dt >= start_search_date if start_search_date is not None else true,
                data_model.dt <= end_search_date if end_search_date is not None else true,
            )
            .order_by(data_model.dt)
        )

        result = await self.db.execute(query)
        return result.all()


    async def get_data_timeseries_by_height(self, station: DataStation, field_name: str, start_search_date, end_search_date):
        query = (
            select(
                func.max(LidarStationData.height).label("height"),
                func.json_agg(
                    aggregate_order_by(#Ordenar subgrupo
                        func.json_build_object(
                            f"{field_name}", getattr(LidarStationData, field_name, None),
                            "dt", LidarStationData.dt
                        ),
                    LidarStationData.dt.asc()#ordenar por
                    ),
                ).label("height_levels")
            )
            .where(
                LidarStationData.station_id == station.id,
                LidarStationData.dt >= start_search_date if start_search_date is not None else true,
                LidarStationData.dt <= end_search_date if end_search_date is not None else true,
            )
            .group_by(
                LidarStationData.height,
                LidarStationData.station_id
            )
            .order_by(LidarStationData.height)
        )

        result = await self.db.execute(query)
        return result.all()
    

    async def get_last_date(self, station_id: UUID, data_model):
        query = select(func.max(data_model.dt).label("last_date")).where(data_model.station_id == station_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()


    async def get_available_months(self, station_id: UUID, data_model):
        month_start = func.date_trunc("month", data_model.dt).label("month_start")
        query = (
            select(month_start)
            .where(data_model.station_id == station_id)
            .group_by(month_start)
            .order_by(month_start.desc())
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())


    async def get_wind_rose_base_data(self, station: DataStation, start_search_date, end_search_date, height=None):
        query = (
            select(
                LidarStationData.height,
                LidarStationData.h_spd,
                LidarStationData.wdir,
                LidarStationData.ti,
            )
            .where(
                LidarStationData.station_id == station.id,
                LidarStationData.dt >= start_search_date if start_search_date is not None else True,
                LidarStationData.dt <= end_search_date if end_search_date is not None else True,
                LidarStationData.height == height if height is not None else True,
            )
            .order_by(LidarStationData.dt)
        )
        result = await self.db.execute(query)
        return result.all()


    async def insert_batch_qualified_data(self, batch: list[dict]):
        if not batch:
            return

        statement = insert(LidarStationData)
        statement = statement.on_conflict_do_update(
            constraint="uq_lidar_station_data_datetime_station_id_height",
            set_={
                "m_temp": statement.excluded.m_temp,
                "m_pres": statement.excluded.m_pres,
                "m_wspd": statement.excluded.m_wspd,
                "m_wdir": statement.excluded.m_wdir,
                "h_spd": statement.excluded.h_spd,
                "ti": statement.excluded.ti,
                "wdir": statement.excluded.wdir,
            },
        )
        await self.db.execute(statement, batch)


    async def insert_batch_solarimetric_data(self, batch: list[dict]):
        if not batch:
            return

        statement = insert(SolarimetricStationData)
        statement = statement.on_conflict_do_update(
            constraint="uq_solarimetric_stations_datetime_station_id",
            set_={
                "ghi": statement.excluded.ghi,
                "hum": statement.excluded.hum,
                "temp": statement.excluded.temp,
                "vel": statement.excluded.vel,
            },
        )
        await self.db.execute(statement, batch)


    async def getHeightByPlatform(self, station: DataStation, start_datetime=None, end_datetime=None):
        query = (
            select(LidarStationData.height)
            .where(
                LidarStationData.station_id == station.id,
                LidarStationData.dt >= start_datetime if start_datetime is not None else true,
                LidarStationData.dt <= end_datetime if end_datetime is not None else true,
            )
            .group_by(LidarStationData.height)
            .order_by(LidarStationData.height)
        )
        result = await self.db.execute(query)
        rows = result.scalars().all()
        return rows


    async def get_hourly_mean_over_days(self, station: DataStation, data_model, field_name: str, start_dt, end_dt):
        avg_expr = self.create_avg_expr(data_model, field_name)
        hour = func.extract("hour", data_model.dt).label("hour")

        if data_model is LidarStationData:
            query = (
                select(
                    LidarStationData.height,
                    hour,
                    avg_expr.label("avg"),
                )
                .where(
                    LidarStationData.station_id == station.id,
                    LidarStationData.dt >= start_dt if start_dt is not None else true,
                    LidarStationData.dt <= end_dt if end_dt is not None else true,
                    getattr(LidarStationData, field_name) != np.nan,
                )
                .group_by(LidarStationData.height, hour)
                .order_by(LidarStationData.height, hour)
            )
        else:
            query = (
                select(
                    hour,
                    avg_expr.label("avg"),
                )
                .where(
                    data_model.station_id == station.id,
                    data_model.dt >= start_dt if start_dt is not None else true,
                    data_model.dt <= end_dt if end_dt is not None else true,
                    getattr(data_model, field_name) != np.nan,
                )
                .group_by(hour)
                .order_by(hour)
            )

        result = await self.db.execute(query)
        return result.all()
    

    async def get_average_by_height(self, station: DataStation, field_name: str, start_search_date, end_search_date):
        avg_expr = self.create_avg_expr(LidarStationData, field_name)
        query = (
            select(
                LidarStationData.height,
                avg_expr.label("avg")
            )
            .where(
                LidarStationData.station_id == station.id,
                LidarStationData.dt >= start_search_date if start_search_date is not None else true,
                LidarStationData.dt <= end_search_date if end_search_date is not None else true,
                getattr(LidarStationData, field_name) != np.nan,
            )
            .group_by(LidarStationData.height)
            .order_by(LidarStationData.height)
        )
        result = await self.db.execute(query)
        return result.all()


    def create_avg_expr(self, data_model, field_name):
        if field_name == "wdir" or field_name == "m_wdir":
            return self.func_avg_dir(data_model, field_name)
        return func.avg(getattr(data_model, field_name))
    

    def func_avg_dir(self, data_model, field_name):
        """
            Converte graus em radianos
            Calcula seno e cosseno, Faz a média, Usa atan2, Converte de volta para graus e Normaliza para 0-360
        """
        angle_deg = (
            func.degrees(#Converter de radianos para graus
                func.atan2(#Reconstruir o ângulo (em radianos)
                    func.avg(func.sin(func.radians(getattr(data_model, field_name)))),#eixo Y → sin(θ) e depois media dos vetores
                    func.avg(func.cos(func.radians(getattr(data_model, field_name))))#eixo X → cos(θ) e depois media dos vetores
                )
            ) + 360 #Garantir valor positivo (De -180 ate +180 para +180 ate +540)
        )
        avg_expr = func.mod(# Intervalo de 0 a 360
            cast(angle_deg, Numeric),#Necessario fazer cast para usar o modulo, PostgreSQL não aceita mod(double precision, integer)
            360
        )
        return avg_expr
    

    async def delete_qualified_data_between_datetimes(self, station: DataStation, start_datetime, end_datetime):        
        statement = delete(LidarStationData).where(
            LidarStationData.station_id == station.id,
            LidarStationData.dt >= start_datetime,
            LidarStationData.dt <= end_datetime
        )
        await self.db.exec(statement)
        return await self.db.commit()


    async def delete_solarimetric_data_between_datetimes(self, station: DataStation, start_datetime, end_datetime):
        statement = delete(SolarimetricStationData).where(
            SolarimetricStationData.station_id == station.id,
            SolarimetricStationData.dt >= start_datetime,
            SolarimetricStationData.dt <= end_datetime,
        )
        await self.db.exec(statement)
        return await self.db.commit()
    
    
    async def commit(self):
        await self.db.commit()
    

    async def rollback(self):
        await self.db.rollback()