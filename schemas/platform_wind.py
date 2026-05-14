from datetime import datetime
from uuid import UUID, uuid4
from pydantic import BaseModel


class CreatePlatform(BaseModel):
    name: str
    sensor_height: float


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
    plat_id: UUID
