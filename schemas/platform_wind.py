from datetime import datetime
from uuid import UUID, uuid4
from pydantic import BaseModel


class CreateDataStation(BaseModel):
    name: str
    sensor_height: float | None = None
    type: UUID
    layer_id: UUID | None = None


class CreatePlatform(CreateDataStation):
    pass


class CreateLidarStationData(BaseModel):
    dt: datetime  #Time and Date
    m_temp: float  # Met Air Temperature  # Temperatura do ar
    m_pres: float  # Met Pressure # Pressão
    m_wspd: float # Met Wind Speed # Velocidade do vento
    m_wdir: float #Met Wind Direction # Direção do Vento
    height: int # Height (m) #ALTURA em M
    h_spd: float # Horizontal Wind Speed #Velocidade do Vento Horizontal
    wdir: float #Met Wind Direction # Direção do Vento
    ti: float  # Turbulence Intensity # Intensidade da turbulência
    station_id: UUID


class CreateQualifiedData(BaseModel):
    dt: datetime  #Time and Date
    m_temp  : float  # Met Air Temperature  # Temperatura do ar
    m_pres : float  # Met Pressure # Pressão
    m_wspd: float # Met Wind Speed # Velocidade do vento
    m_wdir: float #Met Wind Direction # Direção do Vento
    height: int # Height (m) #ALTURA em M
    h_spd: float # Horizontal Wind Speed #Velocidade do Vento Horizontal
    wdir: float #Met Wind Direction # Direção do Vento
    ti : float  # Turbulence Intensity # Intensidade da turbulência
    station_id: UUID


class CreateSolarimetricStationData(BaseModel):
    dt: datetime
    ghi: float
    hum: float
    temp: float
    vel: float
    station_id: UUID
