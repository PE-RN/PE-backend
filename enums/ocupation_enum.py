from enum import Enum


class OcupationEnum(str, Enum):

    INVESTOR = "investidor"
    RESEARCHER = "pesquisador"
    DEVELOPER = "desenvolvedor"
    OTHER = "outro"
