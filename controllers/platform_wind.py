import calendar
import datetime
from typing import Annotated
from fastapi import HTTPException
from fastapi.params import Depends
import numpy as np
from pandas.errors import EmptyDataError
from sqlmodel.ext.asyncio.session import AsyncSession
from schemas.platform_wind import CreateQualifiedData
from sql_app.database import get_db
from sql_app.models import Platform, QualifiedData
import pandas as pd
from uuid import UUID
from scipy.optimize import curve_fit
import re

from repositories.platform_wind import PlatformRepository
from enums.platform_enum import WindRoseMode

fields_without_height_level_dict = {}
fields_without_height_level_dict["m_temp"] = "Temperatura do ar - Met"
fields_without_height_level_dict["m_pres"] = "Pressão - Met"
fields_without_height_level_dict["m_wspd"] = "Velocidade do vento - Met"
fields_without_height_level_dict["m_wdir"] = "Direção do Vento - Met"

import logging
logger = logging.getLogger(__name__)

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
    

    async def create_platform(self, createPlatform):
        try:
            platform_dict = createPlatform.model_dump()
            platform: Platform = Platform(**platform_dict)
            self.repo.insert_platform(platform)
            await self.repo.commit()
            await self.repo.refresh_platform(platform)
            return platform_dict
            # return platform
        except Exception as e:
            await self.repo.rollback()
            raise RuntimeError(f"Erro ao criar plataforma: {str(e)}")
    
        
    async def getPlatform(self, name=None, id=None) -> Platform | None: 
        try:
            platform = await self.repo.get_platform(name,id)
            if platform is None:
                if id is not None:
                    raise LookupError(f"Id {id} da Plataforma é inválido.") 
                else:
                    raise LookupError(f"Plataforma de nome {name} não encontrada.")
            return dict(platform)
        except LookupError:
            raise
        except Exception as e:
            raise RuntimeError(f"Erro ao listar Plataforma: {str(e)}")


    async def list_platforms(self):
        try:
            platforms = await self.repo.list_all_platforms()
            return platforms
        except HTTPException:
            raise
        except Exception as e:
            raise RuntimeError(f"Erro ao listar Plataformas: {str(e)}")


    async def validate_qualified_data_columns(self, df):
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


    async def create_qualified_data_month(self, file_path: str, platform_id: UUID):
        try:
            platform = await self.getPlatform(id=platform_id)
            df = pd.read_csv(file_path, header=0, sep=";", )
            await self.save_qualified_data_to_db(df, platform, file_path)
        except Exception as e:
            logger.warning(f"Erro ao salvos dados mensais de uma plataforma: {str(e)}")
            await self.repo.rollback()
        finally:
            import os
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"[CLEANUP] Arquivo temporário '{file_path}' removido.")
                print(f"[CLEANUP] Arquivo temporário '{file_path}' removido.")
            return


    async def save_qualified_data_to_db(self, df, platform, path_file):
        id_platform = platform["id"]
        sensor_height = int(platform["sensor_height"])
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
            #df_hora = df.resample("1h").mean()

            if df_hora.empty:
                logger.warning(f"[IMPORT] {platform['name']}: Arquivo {path_file} vazio após processamento.")

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
                        "plat_id": id_platform
                    }
                    createQualifildData = CreateQualifiedData(**qualifild_data_dict)#Otimizar
                    create_qualified_data_list_dict.append(createQualifildData)
            await self.create_qualified_data_list(create_qualified_data_list_dict)
            logger.info(f"[INFO] {platform['name']} Dados do arquivo {path_file} salvos com sucesso.")
            print(f"[INFO] {platform['name']} Dados do arquivo {path_file} salvos com sucesso.")
        except Exception as e:
            logger.warning(f"[IMPORT][ERROR] {platform['name']}: Falha ao salvar o arquivo {path_file}. {e}.")


    async def create_qualified_data_list(self, list_data: list[dict]):
        try:
            await self.repo.insert_batch_qualified_data(list_data)
            await self.repo.commit()
        except Exception as e:
            await self.repo.rollback()
            raise RuntimeError(f"Erro ao criar Dados Brutos por lista: {str(e)}")


    async def graphics_time_series_data_by_plataform(self, platform_id, field_name, start_search_date, end_search_date):
        try:
            start_search_date, end_search_date = await self.valide_date_and_create_datetime(platform_id, start_search_date, end_search_date)
            self.verifyFieldNameExistsInDataModel(QualifiedData, field_name)
            platform : Platform = await self.getPlatform(id=platform_id)

            raw_data =  await self.repo.get_data_timeseries_by_height(platform, field_name, start_search_date, end_search_date)
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
        except LookupError as e:
            raise 
        except ValueError as e:
            raise
        except Exception as e:
            raise Exception(f"Erro ao gerar série temporal: {str(e)}")


    def verifyFieldNameExistsInDataModel(self, DataModel, field_name: str):
        if field_name == "plat_id" or field_name == "id" or field_name == "dt" :
            raise ValueError(f"O campo '{field_name}' não pode ser utilizado.")
        if not hasattr(DataModel, field_name):
            raise LookupError(f"O campo '{field_name}' não existe.")
        

    def fist_and_laster_data_month(self, date_time):
        fist_day_datetime = date_time.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        last_day = calendar.monthrange(date_time.year, date_time.month)[1]
        last_day_datetime = date_time.replace(
            day=last_day, hour=23, minute=59, second=59, microsecond=999999
        ) 
        return fist_day_datetime, last_day_datetime


    async def last_month_and_x_heights_wind_rose(self, platform_id, mode, start_search_date, end_search_date, height= None, number_heights=3):
        if mode == WindRoseMode.mean_h_spd:
            field_name = "h_spd"
        elif mode == WindRoseMode.mean_ti:
            field_name = "ti"
        else:
            raise ValueError("Modo de cálculo da rosa dos ventos inválido. Use 'mean_h_spd' ou 'mean_ti'.")

        start_search_date, end_search_date = await self.valide_date_and_create_datetime(platform_id, start_search_date, end_search_date)
        platform:Platform = await self.getPlatform(id=platform_id)
        heights = await self.repo.getHeightByPlatform(platform, start_search_date, end_search_date)
        if height is None:
            if not heights:
                raise ValueError("Nenhuma altura encontrada para a plataforma.")            
            heights = heights[number_heights:]
        else: 
            if height not in heights:
                raise ValueError(f"Altura {height} não encontrada para a plataforma.")
            heights = [height]
        
        
        wind_rose_data = []
        for height in heights:
            data = await self.graphics_wind_rose_data_mean_field_by_platform(platform_id, field_name, start_search_date, end_search_date, height)
            wind_rose_data.append(data)
        return wind_rose_data


    async def graphics_wind_rose_data_mean_field_by_platform(self, platform_id, field_name, start_search_date, end_search_date, height):
        try:
            platform:Platform = await self.getPlatform(id=platform_id)
            raw_data = await self.repo.get_wind_rose_base_data(platform, start_search_date, end_search_date,height)

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
        except LookupError as e:
            raise 
        except ValueError as e:
            raise
        except Exception as e:
            raise Exception(f"Erro ao gerar rosa dos ventos: {str(e)}")


    async def heightsInPlatform(self, platform_id, start_search_date=None, end_search_date=None):
        try:
            if start_search_date is None and end_search_date is None:
                last_date = await self.repo.get_last_date(platform_id)
                if last_date is None:
                    return {"available_heights": []}
                start_search_date, end_search_date = self.fist_and_laster_data_month(last_date)
            elif start_search_date is not None and end_search_date is not None:
                if start_search_date > end_search_date:
                    raise ValueError("A data de início deve ser anterior à data de término.")

            platform:Platform = await self.getPlatform(id=platform_id)
            heights_platform = await self.repo.getHeightByPlatform(platform, start_search_date, end_search_date)
            return {"available_heights": heights_platform}
        except LookupError as e:
            raise 
        except ValueError as e:
            raise
        except Exception as e:
            raise Exception(f"Erro ao listar as alturas em uma plataforma: {str(e)}")


    async def average_vertical_profile(self, platform_id, start_datetime, end_datetime, number_heights:int=3):
        try:
            start_datetime, end_datetime = await self.valide_date_and_create_datetime(platform_id, start_datetime, end_datetime)
            
            platform:Platform = await self.getPlatform(id=platform_id)
            raw_data =  await self.repo.get_average_by_height(platform, "h_spd", start_datetime, end_datetime)
            
            if len(raw_data) <= 1:
                return {
                    "observations" : [{"x":raw_data[0][0], "y":raw_data[0][1]} if len(raw_data) == 1 else {}],
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

            observations = [ { "x": int(h), "y":float(v)} for h, v in raw_data[number_heights:] ]
            curve_continuous_profile_power_law = [
                {"x": 0, "y": 0}] + [ 
                { "x": int(h), "y":float(v)} for h, v in zip(h_continuous , w_speeds_profile_power_law) ]
            curve_continuous_profile_surf_rough = [
                {"x": 0, "y": 0}] + [ 
                { "x": int(h), "y":float(v)} for h, v in zip(h_continuous , w_speeds_profile_surf_rough) ]

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
        except LookupError as e:
            raise 
        except ValueError as e:
            raise
        except Exception as e:
            raise Exception(f"Erro ao calcular Perfil vertical: {str(e)}")


    async def average_diurnal_cycle(self, platform_id, field_name, start_datetime, end_datetime, number_heights:int=3):
            try:

                start_datetime, end_datetime = await self.valide_date_and_create_datetime(platform_id, start_datetime, end_datetime)
                platform:Platform = await self.getPlatform(id=platform_id)

                # Obter as alturas disponíveis
                heights = await self.repo.getHeightByPlatform(platform, start_datetime, end_datetime)
                if not heights:
                    raise ValueError("Nenhuma altura encontrada para a plataforma.")
                
                # Limitar o número de alturas
                heights = heights[number_heights:]

                self.verifyFieldNameExistsInDataModel(QualifiedData, field_name)

                raw_data =  await self.repo.get_hourly_mean_over_days(platform, field_name, start_datetime, end_datetime)
                series = {}
                for row in raw_data:
                    if row.height in heights:
                        key = f"{row.height}m"
                        if key not in series:
                            series[key] = []
                        series[key].append({
                            "x": int(row.hour),
                            "y": float(row.avg)
                        })
                        # series["15m"] = [{"x":0, "y":50}, {"x":1, "y":45}, . . . , {"x":23, "y":85.5} ]

                items =  [{"id": key,"data": list_h_and_mean}  for   key, list_h_and_mean   in series.items()]#chave, valor
                if field_name in fields_without_height_level_dict.keys():
                    items[0]["id"] =  fields_without_height_level_dict[field_name]
                    items = items[0]
                return { "diurnalProfile" : items }
            except LookupError as e:
                raise 
            except ValueError as e:
                raise
            except Exception as e:
                raise Exception(f"Erro ao calcular Perfil diurno: {str(e)}")


    async def delete_qualified_data_between_datetimes(self, platform_id, start_datetime, end_datetime):
        try:
            platform:Platform = await self.getPlatform(id=platform_id)
            await self.repo.delete_qualified_data_between_datetimes(platform, start_datetime, end_datetime)
        except LookupError as e:
            raise 
        except ValueError as e:
            raise
        except Exception as e:
            raise Exception(f"Erro ao excluir dados entre datas: {str(e)}")


    async def valide_date_and_create_datetime(self, platform_id, start_datetime = None, end_datetime = None):
        if start_datetime is None and end_datetime is None:
            last_date = await self.repo.get_last_date(platform_id)
            if not last_date:
                raise LookupError("Nenhuma dado encontrado para a plataforma.")
            start_datetime, end_datetime = self.fist_and_laster_data_month(last_date)
        elif start_datetime is not None and end_datetime is not None:
            if start_datetime > end_datetime:
                raise ValueError("A data de início deve ser anterior à data de término.")
        return start_datetime, end_datetime


def get_height_in_df_by_columns(df: pd.DataFrame):
    heights = []
    for col in df.columns:
        if "Wind Direction (deg) at" in col or "Horizontal Wind Speed (m/s) at" in col:
            num = int("".join(filter(str.isdigit, col)))
            if num not in heights:
                heights.append(num)
    return heights


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