from enum import Enum

class WindRoseMode(str, Enum):
    mean_h_spd = "mean_h_spd"
    mean_ti = "mean_ti"


class FieldsLidarData(str, Enum):
    m_temp = "m_temp"
    m_pres = "m_pres"
    m_wspd = "m_wspd"
    m_wdir = "m_wdir"
    h_spd = "h_spd"
    ti = "ti"


class FieldsSolarimetricStationData(str, Enum):
    ghi = "ghi"
    hum = "hum"
    temp = "temp"
    vel = "vel"

class DataStationType(str, Enum):
    lidar = "lidar"
    solarimetric = "solarimetric"