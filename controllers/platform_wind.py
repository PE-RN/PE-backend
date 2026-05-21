import calendar
import logging
import os
import re
import unicodedata
from typing import Annotated
from uuid import UUID

import numpy as np
import pandas as pd
from fastapi.params import Depends
from scipy.optimize import curve_fit
from sqlmodel.ext.asyncio.session import AsyncSession

from enums.platform_enum import DataStationType, WindRoseMode
from repositories.platform_wind import PlatformRepository
from schemas.platform_wind import CreateDataStation, CreateLidarStationData, CreateQualifiedData, CreateSolarimetricStationData
from sql_app.database import get_db
from sql_app.models import DataStation, LidarStationData, SolarimetricStationData

fields_without_height_level_dict = {}
fields_without_height_level_dict["m_temp"] = "Temperatura do ar - Met"
fields_without_height_level_dict["m_pres"] = "Pressão - Met"
fields_without_height_level_dict["m_wspd"] = "Velocidade do vento - Met"
fields_without_height_level_dict["m_wdir"] = "Direção do Vento - Met"

logger = logging.getLogger(__name__)

LIDAR_HEIGHT_PATTERN = re.compile(
    r"(?:Wind Direction \(deg\)|Horizontal Wind Speed \(m/s\)|TI) at\s+(\d+(?:[\.,]\d+)?)m\b"
)

STATION_TYPE_ALIAS_MAP = {
    "LIDAR": DataStationType.lidar.value,
    "SOLAR": DataStationType.solarimetric.value,
    "SOLARIMETRICA": DataStationType.solarimetric.value,
    "SOLARIMETRIC": DataStationType.solarimetric.value,
}

SOLARIMETRIC_FIELD_ALIAS_MAP = {
    "GHI": "ghi",
    "TEMPERATURA": "temp",
    "UMIDADE": "hum",
    "VELOCIDADE DO VENTO": "vel",
}

LIDAR_FIELD_ALIAS_MAP = {
    "DIRECAO DO VENTO": "wdir",
    "DIRECAO DO VENTO MET": "m_wdir",
    "HORIZONTAL WIND SPEED": "h_spd",
    "INTENSIDADE DA TURBULENCIA": "ti",
    "INTENSIDADE DE TURBULENCIA": "ti",
    "MET AIR TEMP": "m_temp",
    "MET PRESSURE": "m_pres",
    "MET WIND DIRECTION": "m_wdir",
    "MET WIND SPEED": "m_wspd",
    "PRESSAO": "m_pres",
    "TEMPERATURA DO AR": "m_temp",
    "TURBULENCE INTENSITY": "ti",
    "VELOCIDADE DO VENTO": "h_spd",
    "VELOCIDADE DO VENTO HORIZONTAL": "h_spd",
    "VELOCIDADE DO VENTO MET": "m_wspd",
}

class PlatformService:
    def __init__(self, repository: PlatformRepository):
        self.repo = repository

    @staticmethod
    def inject_repository(db: Annotated[AsyncSession, Depends(get_db)]) -> PlatformRepository:
        return PlatformRepository(db=db)
    
    @staticmethod
    def inject_service(repository: Annotated[PlatformRepository, Depends(inject_repository)]) -> "PlatformService":
        print("Injetando serviço UserService...")
        return PlatformService(repository=repository)
    

    async def create_data_station(self, create_data_station: CreateDataStation) -> DataStation:
        try:
            existing_station = await self.repo.get_platform(name=create_data_station.name)
            if existing_station is not None:
                raise ValueError(f"Já existe uma estação com o nome '{create_data_station.name}'.")

            station_type = await self.repo.get_station_type(create_data_station.type)
            if station_type is None:
                raise ValueError("O tipo informado para a estação é inválido.")

            station = DataStation(**create_data_station.model_dump())
            self.repo.insert_platform(station)
            await self.repo.commit()
            await self.repo.refresh_platform(station)
            return station
        except Exception as e:
            await self.repo.rollback()
            if isinstance(e, ValueError):
                raise
            raise RuntimeError(f"Erro ao criar estação: {str(e)}")


    async def create_platform(self, create_platform: CreateDataStation) -> DataStation:
        return await self.create_data_station(create_platform)
    
        
    async def get_data_station(self, name=None, id=None, layer_id=None, station_type=None) -> DataStation:
        try:
            station = None

            if id is not None and name is None and layer_id is None:
                station = await self.repo.get_platform(id=id, station_type=station_type)
                if station is None:
                    station = await self.repo.get_platform(layer_id=id, station_type=station_type)
            else:
                station = await self.repo.get_platform(name=name, id=id, layer_id=layer_id, station_type=station_type)

            if station is None:
                if id is not None:
                    raise LookupError(f"Id ou layer_id {id} da estação é inválido.")
                if name is not None and layer_id is not None:
                    raise LookupError(f"Estação '{name}' não encontrada para a camada informada.")
                if name is not None:
                    raise LookupError(f"Estação de nome {name} não encontrada.")
                raise LookupError("Estação não encontrada.")
            return station
        except LookupError:
            raise
        except Exception as e:
            raise RuntimeError(f"Erro ao buscar estação: {str(e)}")


    async def getPlatform(self, name=None, id=None) -> DataStation:
        return await self.get_data_station(name=name, id=id)


    async def list_data_stations(self, name=None, layer_id=None, station_type=None):
        try:
            return await self.repo.list_all_platforms(name=name, layer_id=layer_id, station_type=station_type)
        except Exception as e:
            raise RuntimeError(f"Erro ao listar estações: {str(e)}")


    async def list_platforms(self):
        return await self.list_data_stations()


    async def validate_lidar_data_columns(self, df):
        required_columns = [
            "Time and Date",
            "Met Air Temp. (C)",
            "Met Pressure (mbar)",
            "Met Wind Speed (m/s)",
            "Met Wind Direction (deg)",
        ]

        missing_columns = []

        # valida colunas fixas
        for col in required_columns:
            if col not in df.columns:
                missing_columns.append(col)

        # valida colunas dinâmicas
        has_wdir = False
        has_hspd = False
        has_ti = False

        for col in df.columns:
            if re.fullmatch(r"Wind Direction \(deg\) at \d+m", col):
                has_wdir = True
            elif re.fullmatch(r"Horizontal Wind Speed \(m/s\) at \d+m", col):
                has_hspd = True
            elif re.fullmatch(r"TI at \d+m", col):
                has_ti = True

        if not has_wdir:
            missing_columns.append("Wind Direction (deg) at Xm")

        if not has_hspd:
            missing_columns.append("Horizontal Wind Speed (m/s) at Xm")

        if not has_ti:
            missing_columns.append("TI at Xm")
        
        if missing_columns:
            raise ValueError(f"As seguintes colunas estão ausentes: {missing_columns}")


    async def validate_qualified_data_columns(self, df):
        await self.validate_lidar_data_columns(df)


    async def validate_solarimetric_data_columns(self, df):
        required_columns = [
            "TIMESTAMP",
            "GHI",
            "UMIDADE",
            "VELOCIDADE DO VENTO",
            "TEMPERATURA",
        ]

        missing_columns = [column for column in required_columns if column not in df.columns]
        if missing_columns:
            raise ValueError(f"As seguintes colunas estão ausentes: {missing_columns}")


    async def create_lidar_data_month(self, file_path: str, station_id: UUID):
        try:
            station = await self.get_data_station(id=station_id)
            self.require_station_type(station, DataStationType.lidar)

            df = pd.read_csv(file_path, header=0, sep=";", )
            await self.save_lidar_data_to_db(df, station, file_path)
        except Exception as e:
            logger.warning(f"Erro ao salvar dados mensais da estação lidar: {str(e)}")
            await self.repo.rollback()
        finally:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"[CLEANUP] Arquivo temporário '{file_path}' removido.")
                print(f"[CLEANUP] Arquivo temporário '{file_path}' removido.")
            return


    async def create_qualified_data_month(self, file_path: str, platform_id: UUID):
        await self.create_lidar_data_month(file_path, platform_id)


    async def create_solarimetric_data_month(self, file_path: str, station_id: UUID):
        try:
            station = await self.get_data_station(id=station_id)
            self.require_station_type(station, DataStationType.solarimetric)

            df = pd.read_csv(file_path, header=0)
            await self.save_solarimetric_data_to_db(df, station, file_path)
        except Exception as e:
            logger.warning(f"Erro ao salvar dados mensais da estação solarimétrica: {str(e)}")
            await self.repo.rollback()
        finally:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"[CLEANUP] Arquivo temporário '{file_path}' removido.")
                print(f"[CLEANUP] Arquivo temporário '{file_path}' removido.")
            return


    async def save_lidar_data_to_db(self, df, station: DataStation, path_file):
        station_id = station.id
        station_name = station.name
        sensor_height = int(station.sensor_height or 0)
        try:
            df["Time and Date"] = pd.to_datetime(df["Time and Date"])
            df = df.replace(",", ".", regex=True)
            for col in df.columns:
                if col != "Time and Date":
                    df[col] = pd.to_numeric(df[col], errors="coerce")

            df = df.set_index("Time and Date").sort_index()

            agg_dict = {}
            target_col_deg = "Wind Direction (deg)"

            for col in df.columns:
                if target_col_deg in col:
                    agg_dict[col] = mean_wind_direction #Media vetorial, ignora os nan
                else:
                    agg_dict[col] = "mean" #Media simples, ignora os nan

            df_hora = df.resample("1h").agg(agg_dict)
            df_hora = df_hora.dropna(how="all")

            if df_hora.empty:
                logger.warning(f"[IMPORT] {station_name}: Arquivo {path_file} vazio após processamento.")

            heights = get_height_in_df_by_columns(df)

            create_qualified_data_list_dict = []
            for index, row in df_hora.iterrows():
                for height in heights: 
                    final_height = height + sensor_height

                    qualifild_data_dict = {
                        "dt": index,
                        "m_temp": row.get("Met Air Temp. (C)", np.nan),
                        "m_pres": row.get("Met Pressure (mbar)", np.nan),
                        "m_wspd": row.get("Met Wind Speed (m/s)", np.nan),
                        "m_wdir": row.get("Met Wind Direction (deg)", np.nan),
                        "height": final_height,
                        "wdir": row.get(f"Wind Direction (deg) at {height}m", np.nan),
                        "h_spd": row.get(f"Horizontal Wind Speed (m/s) at {height}m", np.nan),
                        "ti": row.get(f"TI at {height}m", np.nan),
                        "station_id": station_id,
                    }
                    create_lidar_data = CreateLidarStationData(**qualifild_data_dict)
                    create_qualified_data_list_dict.append(create_lidar_data.model_dump())

            create_qualified_data_list_dict = dedupe_lidar_batch_rows(
                create_qualified_data_list_dict,
                station_name,
                path_file,
            )

            await self.create_lidar_data_list(create_qualified_data_list_dict)
            logger.info(f"[INFO] {station_name} Dados do arquivo {path_file} salvos com sucesso.")
            print(f"[INFO] {station_name} Dados do arquivo {path_file} salvos com sucesso.")
        except Exception as e:
            logger.warning(f"[IMPORT][ERROR] {station_name}: Falha ao salvar o arquivo {path_file}. {e}.")


    async def save_qualified_data_to_db(self, df, platform, path_file):
        await self.save_lidar_data_to_db(df, platform, path_file)


    async def save_solarimetric_data_to_db(self, df, station: DataStation, path_file):
        station_id = station.id
        station_name = station.name
        try:
            await self.validate_solarimetric_data_columns(df)

            df["TIMESTAMP"] = pd.to_datetime(df["TIMESTAMP"])
            numeric_columns = ["GHI", "UMIDADE", "VELOCIDADE DO VENTO", "TEMPERATURA"]
            for column in numeric_columns:
                df[column] = pd.to_numeric(df[column], errors="coerce")

            df = df.set_index("TIMESTAMP").sort_index()
            df_hourly = df.resample("1h").mean().dropna(how="all")

            if df_hourly.empty:
                logger.warning(f"[IMPORT] {station_name}: Arquivo {path_file} vazio após processamento.")

            rows = []
            for index, row in df_hourly.iterrows():
                station_data = CreateSolarimetricStationData(
                    dt=index,
                    ghi=row.get("GHI", np.nan),
                    hum=row.get("UMIDADE", np.nan),
                    temp=row.get("TEMPERATURA", np.nan),
                    vel=row.get("VELOCIDADE DO VENTO", np.nan),
                    station_id=station_id,
                )
                rows.append(station_data.model_dump())

            await self.create_solarimetric_data_list(rows)
            logger.info(f"[INFO] {station_name} Dados do arquivo {path_file} salvos com sucesso.")
            print(f"[INFO] {station_name} Dados do arquivo {path_file} salvos com sucesso.")
        except Exception as e:
            logger.warning(f"[IMPORT][ERROR] {station_name}: Falha ao salvar o arquivo {path_file}. {e}.")


    async def create_lidar_data_list(self, list_data: list[dict]):
        try:
            await self.repo.insert_batch_qualified_data(list_data)
            await self.repo.commit()
        except Exception as e:
            await self.repo.rollback()
            raise RuntimeError(f"Erro ao criar dados lidar por lista: {str(e)}")


    async def create_qualified_data_list(self, list_data: list[dict]):
        await self.create_lidar_data_list(list_data)


    async def create_solarimetric_data_list(self, list_data: list[dict]):
        try:
            await self.repo.insert_batch_solarimetric_data(list_data)
            await self.repo.commit()
        except Exception as e:
            await self.repo.rollback()
            raise RuntimeError(f"Erro ao criar dados solarimétricos por lista: {str(e)}")


    async def graphics_time_series_data_by_lidar(self, platform_id, field_name, start_search_date, end_search_date):
        try:
            station: DataStation = await self.get_data_station(id=platform_id)
            self.require_station_type(station, DataStationType.lidar)
            field_name = self.resolve_field_name_for_station(station, field_name)
            start_search_date, end_search_date = await self.valide_date_and_create_datetime(station, LidarStationData, start_search_date, end_search_date)

            raw_data =  await self.repo.get_data_timeseries_by_height(station, field_name, start_search_date, end_search_date)
            formatted = []
            for row in raw_data:
                # if row[0] in heights:
                list_values_by_height = []
                for height in row.height_levels:
                    
                    data_dict = {}
                    data_dict[f"x"] = height['dt']
                    data_dict[f"y"] = height[f'{field_name}'] if height[f'{field_name}'] != "NaN" else None
                    list_values_by_height.append(data_dict)

                formatted.append({
                        "id": f"{row.height}m" ,
                        "data": list_values_by_height}
                )

                if field_name in fields_without_height_level_dict.keys():
                    formatted[0]["id"] =  fields_without_height_level_dict[field_name] #Sem alturas
                    break
            
            return {"timeSeries": formatted}
        except LookupError:
            raise 
        except ValueError:
            raise
        except Exception as e:
            raise Exception(f"Erro ao gerar série temporal: {str(e)}")
        

    async def graphics_time_series_data(self, station_id, field_name, start_search_date, end_search_date):
        try:
            station: DataStation = await self.get_data_station(id=station_id)
            self.require_station_type(station, DataStationType.solarimetric)
            field_name = self.resolve_field_name_for_station(station, field_name)
            start_search_date, end_search_date = await self.valide_date_and_create_datetime(station, SolarimetricStationData, start_search_date, end_search_date)

            raw_data = await self.repo.get_data_timeseries(station, SolarimetricStationData, field_name, start_search_date, end_search_date)
            formatted = []
            for row in raw_data:
                formatted.append({
                    "x": row.dt,
                    "y": row.value if row.value != "NaN" else None,
                })

            return {"timeSeries": [{"id": station.name, "data": formatted}]}
        except LookupError:
            raise
        except ValueError:
            raise
        except Exception as e:
            raise Exception(f"Erro ao gerar série temporal: {str(e)}")


    async def graphics_time_series_by_station(self, station_id, field_name, start_search_date, end_search_date):
        station: DataStation = await self.get_data_station(id=station_id)
        station_type = self.get_station_type_name(station)
        if station_type == DataStationType.lidar.value:
            return await self.graphics_time_series_data_by_lidar(station_id, field_name, start_search_date, end_search_date)
        return await self.graphics_time_series_data(station_id, field_name, start_search_date, end_search_date)


    def verifyFieldNameExistsInDataModel(self, DataModel, field_name: str):
        if field_name in {"id", "dt", "plat_id", "station_id"}:
            raise ValueError(f"O campo '{field_name}' não pode ser utilizado.")
        if not hasattr(DataModel, field_name):
            raise LookupError(f"O campo '{field_name}' não existe.")


    def normalize_lookup_key(self, value: str) -> str:
        normalized = unicodedata.normalize("NFKD", str(value))
        normalized = normalized.encode("ascii", "ignore").decode("ascii")
        normalized = normalized.replace("_", " ")
        normalized = re.sub(r"\s+", " ", normalized.strip())
        return normalized.upper()


    def get_station_type_name(self, station: DataStation) -> str:
        raw_name = station.station_type_ref.name if station.station_type_ref is not None else None
        if not raw_name:
            raise ValueError("A estação informada não possui um tipo associado.")

        normalized = self.normalize_lookup_key(raw_name)
        return STATION_TYPE_ALIAS_MAP.get(normalized, raw_name.strip().lower())


    def require_station_type(self, station: DataStation, expected_type: DataStationType) -> None:
        station_type = self.get_station_type_name(station)
        if station_type != expected_type.value:
            raise ValueError(f"A estação '{station.name}' não é do tipo '{expected_type.value}'.")


    def resolve_field_name_for_station(self, station: DataStation, field_name: str) -> str:
        requested_field = getattr(field_name, "value", field_name)
        station_type = self.get_station_type_name(station)
        data_model = LidarStationData if station_type == DataStationType.lidar.value else SolarimetricStationData

        if hasattr(data_model, requested_field):
            self.verifyFieldNameExistsInDataModel(data_model, requested_field)
            return requested_field

        normalized_field = self.normalize_lookup_key(requested_field)
        alias_map = LIDAR_FIELD_ALIAS_MAP if data_model is LidarStationData else SOLARIMETRIC_FIELD_ALIAS_MAP
        resolved_field = alias_map.get(normalized_field)
        if resolved_field is None:
            raise LookupError(f"O campo '{requested_field}' não existe para o tipo da estação.")

        self.verifyFieldNameExistsInDataModel(data_model, resolved_field)
        return resolved_field
        

    def fist_and_laster_data_month(self, date_time):
        fist_day_datetime = date_time.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        last_day = calendar.monthrange(date_time.year, date_time.month)[1]
        last_day_datetime = date_time.replace(
            day=last_day, hour=23, minute=59, second=59, microsecond=999999
        ) 
        return fist_day_datetime, last_day_datetime


    async def list_available_months(self, platform_id):
        station: DataStation = await self.get_data_station(id=platform_id)
        station_type = self.get_station_type_name(station)
        data_model = LidarStationData if station_type == DataStationType.lidar.value else SolarimetricStationData

        last_date = await self.repo.get_last_date(station.id, data_model)
        if not last_date:
            raise LookupError("Nenhum dado encontrado para a estação.")

        month_starts = await self.repo.get_available_months(station.id, data_model)
        available_months = []
        for month_start in month_starts:
            start_datetime, end_datetime = self.fist_and_laster_data_month(month_start)
            available_months.append(
                {
                    "key": month_start.strftime("%Y-%m"),
                    "start_datetime": start_datetime,
                    "end_datetime": end_datetime,
                }
            )

        default_start_datetime, default_end_datetime = self.fist_and_laster_data_month(last_date)
        return {
            "default_period": {
                "start_datetime": default_start_datetime,
                "end_datetime": default_end_datetime,
            },
            "available_months": available_months,
        }


    async def last_month_and_x_heights_wind_rose(self, platform_id, mode, start_search_date, end_search_date, height= None, number_heights=3):
        if mode == WindRoseMode.mean_h_spd:
            field_name = "h_spd"
        elif mode == WindRoseMode.mean_ti:
            field_name = "ti"
        else:
            raise ValueError("Modo de cálculo da rosa dos ventos inválido. Use 'mean_h_spd' ou 'mean_ti'.")

        station: DataStation = await self.get_data_station(id=platform_id)
        self.require_station_type(station, DataStationType.lidar)
        start_search_date, end_search_date = await self.valide_date_and_create_datetime(station, LidarStationData, start_search_date, end_search_date)
        heights = await self.repo.getHeightByPlatform(station, start_search_date, end_search_date)
        if height is None:
            if not heights:
                raise ValueError("Nenhuma altura encontrada para a estação.")            
            heights = heights[number_heights:]
        else: 
            if height not in heights:
                raise ValueError(f"Altura {height} não encontrada para a estação.")
            heights = [height]
        
        
        wind_rose_data = []
        for height in heights:
            data = await self.graphics_wind_rose_data_mean_field_by_platform(platform_id, field_name, start_search_date, end_search_date, height)
            wind_rose_data.append(data)
        return wind_rose_data


    async def graphics_wind_rose_data_mean_field_by_platform(self, platform_id, field_name, start_search_date, end_search_date, height):
        try:
            station: DataStation = await self.get_data_station(id=platform_id)
            self.require_station_type(station, DataStationType.lidar)
            raw_data = await self.repo.get_wind_rose_base_data(station, start_search_date, end_search_date, height)

            # Extrai arrays
            wdir = np.array([row.wdir for row in raw_data], dtype=np.float64)
            values = np.array([getattr(row, field_name, np.nan) for row in raw_data], dtype=np.float64)

            # Remove NaN
            mask = ~np.isnan(values) & ~np.isnan(wdir)#True somente onde os dois valores são válidos.
            wdir = wdir[mask] #Onde é falso é removido
            values = values[mask]

            wdir = np.mod(wdir, 360)
            bins = (wdir // 15).astype(int) #Calcula o bin (0-11), cada bin = 30 graus, usando o mod
            
            bins = np.clip(bins, 0, 23) # Remover os bins que não estiverem no intervalo de 0 a 11
            sum_per_bin = np.bincount(bins, weights=values, minlength=24) # Soma os valores agrupados por índice.
            
            count_per_bin = np.bincount(bins, minlength=24) # Conta as ocorencias dos bins (conta a quantidade por bin)
            formatted = []
            total_count = int(np.sum(count_per_bin)) if count_per_bin.size > 0 else 0

            
            if (count_per_bin[0] + count_per_bin[23]) > 0:
                avg = (sum_per_bin[0]+sum_per_bin[23]) /  (count_per_bin[0] + count_per_bin[23]) # 1 Bin (345 a 15, Norte)
            else:
                avg = 0
            formatted.append({ "Direcao": 0, "avg": avg})

            for i in range(1, 23, 2):
                direction = (i * 15) +15 #Centralizar direção
                if (count_per_bin[i] + count_per_bin[i+1]) > 0:
                    avg = (sum_per_bin[i]+sum_per_bin[i+1]) /  (count_per_bin[i] + count_per_bin[i+1])
                else:
                    avg = 0

                formatted.append({ "Direcao": direction, "avg": float(avg) })
            return {"height": height, "windRose": formatted}
        except LookupError:
            raise 
        except ValueError:
            raise
        except Exception as e:
            raise Exception(f"Erro ao gerar rosa dos ventos: {str(e)}")


    async def heightsInPlatform(self, platform_id, start_search_date=None, end_search_date=None):
        try:
            station: DataStation = await self.get_data_station(id=platform_id)
            self.require_station_type(station, DataStationType.lidar)

            if start_search_date is None and end_search_date is None:
                last_date = await self.repo.get_last_date(station.id, LidarStationData)
                if last_date is None:
                    return {"available_heights": []}
                start_search_date, end_search_date = self.fist_and_laster_data_month(last_date)
            elif start_search_date is not None and end_search_date is not None:
                if start_search_date > end_search_date:
                    raise ValueError("A data de início deve ser anterior à data de término.")

            heights_platform = await self.repo.getHeightByPlatform(station, start_search_date, end_search_date)
            return {"available_heights": heights_platform}
        except LookupError:
            raise 
        except ValueError:
            raise
        except Exception as e:
            raise Exception(f"Erro ao listar as alturas em uma estação: {str(e)}")


    async def average_vertical_profile(self, platform_id, start_datetime, end_datetime, number_heights:int=3):
        try:
            station: DataStation = await self.get_data_station(id=platform_id)
            self.require_station_type(station, DataStationType.lidar)
            start_datetime, end_datetime = await self.valide_date_and_create_datetime(station, LidarStationData, start_datetime, end_datetime)
            
            raw_data =  await self.repo.get_average_by_height(station, "h_spd", start_datetime, end_datetime)
            
            if len(raw_data) <= 1:
                return {
                    "observations" : [{"y":raw_data[0][0], "x":raw_data[0][1]} if len(raw_data) == 1 else {}],
                    "models_fit" : []
                }
            heights_measured = np.array([float(r[0]) for r in raw_data])#Altura
            w_speeds_measured = np.array([float(r[1]) for r in raw_data])#velocidades medidas nessas alturas

            # Modelo Power Law Exponent
            def power_law_exponent(z, beta, alpha):
                return beta * z**alpha

            params, covariance = curve_fit(power_law_exponent, heights_measured, w_speeds_measured )# Devolve os parametros beta e alpha ajustados em "params"
            beta, alpha = params #separar paremetros

            h_continuous = np.arange(1, 251, 1)#Tentar comecar em 0
            w_speeds_profile_power_law = power_law_exponent(h_continuous , beta, alpha)#Previsoes das alturas de 1 a 250

            w_speeds_predicted_power_law  = power_law_exponent(heights_measured, beta, alpha)

            n = len(w_speeds_measured )
            
            # -------- Erros --------
            rmse_power_law, bias_power_law, r2_power_law = calculate_rmse_bias_r2(w_speeds_predicted_power_law, w_speeds_measured)
            
            log_heights = np.log(heights_measured)
            log_h_continuous = np.log(h_continuous)
            # Modelo linear: U = m * ln(z) + b
            def log_linear_model(log_z, slope, intercept):
                return slope * log_z + intercept

            params, covariance = curve_fit(log_linear_model, log_heights, w_speeds_measured)
            slope, intercept = params
            z0 = np.exp(-intercept / slope)
            w_speeds_predicted_surf_rough = log_linear_model(log_heights, slope, intercept)
            w_speeds_profile_surf_rough = log_linear_model(log_h_continuous, slope, intercept)
            rmse_surf_rough, bias_surf_rough, r2_surf_rough = calculate_rmse_bias_r2(w_speeds_predicted_surf_rough, w_speeds_measured)

            observations = [ { "y": int(h), "x":float(v)} for h, v in raw_data[number_heights:] ]
            curve_continuous_profile_power_law = [
                {"y": 0, "x": 0}] + [ 
                { "y": int(h), "x":float(v)} for h, v in zip(h_continuous , w_speeds_profile_power_law) ]
            curve_continuous_profile_surf_rough = [
                {"y": 0, "x": 0}] + [ 
                { "y": int(h), "x":float(v)} for h, v in zip(h_continuous , w_speeds_profile_surf_rough) ]

            return { 
                "observations" : observations,
                "models_fit" : [
                    {   "id": "Power Law Exponent",
                        "rmse": rmse_power_law,
                        "bias": bias_power_law,
                        "alpha": alpha,
                        "r2" : r2_power_law,
                        "curve":curve_continuous_profile_power_law,
                    },
                    {   "id": "Surface Roughness",
                        "rmse": rmse_surf_rough,
                        "bias": bias_surf_rough,
                        "z0": z0,
                        "r2": r2_surf_rough,
                        "curve":curve_continuous_profile_surf_rough,
                    }
                ]
            } 
        except LookupError:
            raise 
        except ValueError:
            raise
        except Exception as e:
            raise Exception(f"Erro ao calcular Perfil vertical: {str(e)}")


    async def average_diurnal_cycle(self, platform_id, field_name, start_datetime, end_datetime, number_heights:int=3):
            try:

                station: DataStation = await self.get_data_station(id=platform_id)
                station_type = self.get_station_type_name(station)
                data_model = LidarStationData if station_type == DataStationType.lidar.value else SolarimetricStationData
                resolved_field_name = self.resolve_field_name_for_station(station, field_name)
                start_datetime, end_datetime = await self.valide_date_and_create_datetime(station, data_model, start_datetime, end_datetime)

                if data_model is LidarStationData:
                    heights = await self.repo.getHeightByPlatform(station, start_datetime, end_datetime)
                    if not heights:
                        raise ValueError("Nenhuma altura encontrada para a estação.")

                    heights = heights[number_heights:]
                    raw_data = await self.repo.get_hourly_mean_over_days(station, LidarStationData, resolved_field_name, start_datetime, end_datetime)
                    series = {}
                    for row in raw_data:
                        if row.height in heights:
                            key = f"{row.height}m"
                            if key not in series:
                                series[key] = []
                            series[key].append({
                                "x": int(row.hour),
                                "y": float(row.avg),
                            })

                    items = [{"id": key, "data": list_h_and_mean} for key, list_h_and_mean in series.items()]
                    if resolved_field_name in fields_without_height_level_dict.keys() and items:
                        items[0]["id"] = fields_without_height_level_dict[resolved_field_name]
                        items = items[0]
                    return {"diurnalProfile": items}

                raw_data = await self.repo.get_hourly_mean_over_days(station, SolarimetricStationData, resolved_field_name, start_datetime, end_datetime)
                items = [{
                    "x": int(row.hour),
                    "y": float(row.avg),
                } for row in raw_data]
                return {"diurnalProfile": {"id": station.name, "data": items}}
            except LookupError:
                raise 
            except ValueError:
                raise
            except Exception as e:
                raise Exception(f"Erro ao calcular Perfil diurno: {str(e)}")


    async def delete_qualified_data_between_datetimes(self, platform_id, start_datetime, end_datetime):
        try:
            station: DataStation = await self.get_data_station(id=platform_id)
            self.require_station_type(station, DataStationType.lidar)
            await self.repo.delete_qualified_data_between_datetimes(station, start_datetime, end_datetime)
        except LookupError:
            raise 
        except ValueError:
            raise
        except Exception as e:
            raise Exception(f"Erro ao excluir dados entre datas: {str(e)}")


    async def delete_solarimetric_data_between_datetimes(self, station_id, start_datetime, end_datetime):
        try:
            station: DataStation = await self.get_data_station(id=station_id)
            self.require_station_type(station, DataStationType.solarimetric)
            await self.repo.delete_solarimetric_data_between_datetimes(station, start_datetime, end_datetime)
        except LookupError:
            raise
        except ValueError:
            raise
        except Exception as e:
            raise Exception(f"Erro ao excluir dados solarimétricos entre datas: {str(e)}")


    async def valide_date_and_create_datetime(self, station: DataStation, data_model, start_datetime = None, end_datetime = None):
        if start_datetime is None and end_datetime is None:
            last_date = await self.repo.get_last_date(station.id, data_model)
            if not last_date:
                raise LookupError("Nenhum dado encontrado para a estação.")
            start_datetime, end_datetime = self.fist_and_laster_data_month(last_date)
        elif start_datetime is not None and end_datetime is not None:
            if start_datetime > end_datetime:
                raise ValueError("A data de início deve ser anterior à data de término.")
        return start_datetime, end_datetime


def get_height_in_df_by_columns(df: pd.DataFrame):
    heights = []
    for col in df.columns:
        parsed_height = parse_lidar_height_from_column(col)
        if parsed_height is not None and parsed_height not in heights:
            heights.append(parsed_height)
    return heights


def parse_lidar_height_from_column(column_name: str) -> int | None:
    match = LIDAR_HEIGHT_PATTERN.search(str(column_name))
    if match is None:
        return None

    raw_height = match.group(1).replace(",", ".")
    height_value = float(raw_height)
    if not height_value.is_integer():
        raise ValueError(
            f"A altura '{column_name}' não é inteira e não pode ser persistida no formato atual."
        )
    return int(height_value)


def dedupe_lidar_batch_rows(list_data: list[dict], station_name: str, path_file: str) -> list[dict]:
    unique_rows: dict[tuple[object, object, object], dict] = {}
    duplicate_keys: list[tuple[object, object, object]] = []

    for row in list_data:
        key = (row["dt"], row["station_id"], row["height"])
        if key in unique_rows:
            duplicate_keys.append(key)
        unique_rows[key] = row

    if duplicate_keys:
        preview_keys = ", ".join(
            f"({dt}, {height})" for dt, _, height in duplicate_keys[:5]
        )
        logger.warning(
            "[IMPORT][DUPLICATE-BATCH] %s: %s chaves duplicadas geradas ao processar %s. Exemplos: %s",
            station_name,
            len(duplicate_keys),
            path_file,
            preview_keys,
        )

    return list(unique_rows.values())


def mean_wind_direction(series):
    rad = np.deg2rad(series.dropna())
    sin_mean = np.mean(np.sin(rad))
    cos_mean = np.mean(np.cos(rad))
    angle = np.arctan2(sin_mean, cos_mean)
    deg = np.rad2deg(angle)
    return (deg + 360) % 360 # garantir entre 0 e 360


def calculate_rmse_bias_r2(predicted:np.ndarray, measured:np.ndarray ):
    # Calculate RMSE, BIAS and R2
    # soma dos valores reais (observacões)
    n = measured.sum()
    rmse = np.sqrt(np.sum((predicted  - measured )**2) / n)
    bias = np.sum(predicted  - measured ) / n
    # Soma dos quadrados dos resíduos (erro do modelo)
    ss_res = np.sum((measured - predicted)**2)
    # Soma total dos quadrados (variabilidade dos dados)
    ss_tot = np.sum((measured - np.mean(measured))**2)
    # Coeficiente de determinação R2
    # Mede o quão bem a Weibull explica o histograma
    r2 = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0.0
    return rmse, bias, r2