from enum import Enum

class WindRoseMode(str, Enum):
    mean_h_spd = "mean_h_spd"
    mean_ti = "mean_ti"


class FieldsQualifiedData(str, Enum):
    m_temp = "m_temp"
    m_pres = "m_pres"
    m_wspd = "m_wspd"
    m_wdir = "m_wdir"
    h_spd = "h_spd"
    ti = "ti"