from datetime import datetime
from uuid import UUID, uuid4

from typing import List, Optional
import sqlalchemy.dialects.postgresql as pg
from sqlmodel import Column, Field, SQLModel, Relationship, UniqueConstraint


class LayerGroups(SQLModel, table=True):
    __tablename__ = "layer_group"

    id: UUID = Field(
        sa_column=Column(pg.UUID, primary_key=True, unique=True, default=uuid4)
    )

    created_at: datetime = Field(sa_column=Column(pg.TIMESTAMP, default=datetime.now))
    updated_at: datetime = Field(sa_column=Column(pg.TIMESTAMP, default=datetime.now))
    deleted_at: datetime = Field(sa_column=Column(pg.TIMESTAMP, default=None, nullable=True))

    name: str = Field(index=True)
    position: int = Field(default=0, nullable=False)
    layer_group_id: UUID | None = Field(
        default=None, foreign_key="layer_group.id"
    )

class Layer(SQLModel, table=True):
    __tablename__ = "Layer"

    id: UUID = Field(
        sa_column=Column(pg.UUID, primary_key=True, unique=True, default=uuid4)
    )
    created_at: datetime = Field(sa_column=Column(pg.TIMESTAMP, default=datetime.now))
    updated_at: datetime = Field(sa_column=Column(pg.TIMESTAMP, default=datetime.now))
    deleted_at: datetime = Field(sa_column=Column(pg.TIMESTAMP, default=None, nullable=True))

    name: str = Field(index=True)
    subtitle: str
    path_icon: str
    path: str
    activated: bool = False
    layer_group_id: UUID = Field(foreign_key="layer_group.id")

class GroupPermissionLink(SQLModel, table=True):
    group_id: UUID | None = Field(default=None, foreign_key="Groups.id", primary_key=True)
    permission_id: UUID | None = Field(default=None, foreign_key="permissions.id", primary_key=True)


class Group(SQLModel, table=True):

    """
    This class represents a group in database
    """

    __tablename__ = "Groups"

    id: UUID = Field(
        sa_column=Column(pg.UUID, primary_key=True, unique=True, default=uuid4)
    )
    created_at: datetime = Field(sa_column=Column(pg.TIMESTAMP, default=datetime.now))
    updated_at: datetime = Field(sa_column=Column(pg.TIMESTAMP, default=datetime.now))
    deleted_at: datetime = Field(sa_column=Column(pg.TIMESTAMP, default=None, nullable=True))
    name: str = Field(index=True)
    description: str
    users: list["User"] = Relationship(back_populates="group")
    anonymous_users: list["AnonymousUser"] = Relationship(back_populates="group")
    permissions: list["Permission"] = Relationship(back_populates="groups", link_model=GroupPermissionLink)


class Permission(SQLModel, table=True):

    """
    This class represents a permissions in database
    """

    __tablename__ = "permissions"

    id: UUID = Field(
        sa_column=Column(pg.UUID, primary_key=True, unique=True, default=uuid4)
    )
    created_at: datetime = Field(sa_column=Column(pg.TIMESTAMP, default=datetime.now))
    updated_at: datetime = Field(sa_column=Column(pg.TIMESTAMP, default=datetime.now))
    deleted_at: datetime = Field(sa_column=Column(pg.TIMESTAMP, default=None, nullable=True))
    name: str = Field(index=True)
    description: str
    groups: list["Group"] = Relationship(back_populates="permissions", link_model=GroupPermissionLink)


class TemporaryUser(SQLModel, table=True):

    """
    This class represents a  temporary user in database without validate a email
    this users will be deleted with a backouground scheduled task if not confirm the email address
    """

    __tablename__ = "Temporary_Users"

    id: UUID = Field(
        sa_column=Column(pg.UUID, primary_key=True, unique=True, default=uuid4)
    )
    created_at: datetime = Field(sa_column=Column(pg.TIMESTAMP, default=datetime.now))
    updated_at: datetime = Field(sa_column=Column(pg.TIMESTAMP, default=datetime.now))
    deleted_at: datetime = Field(sa_column=Column(pg.TIMESTAMP, default=None, nullable=True))
    email: str = Field(index=True, unique=True)
    password: str
    ocupation: str
    group_id: UUID | None = Field(
        default=None,
        foreign_key="Groups.id"
    )
    gender: str
    education: str
    institution: str
    age: str
    user: str


class User(SQLModel, table=True):

    """
    This class represents a user in database
    """

    __tablename__ = "Users"

    id: UUID = Field(
        sa_column=Column(pg.UUID, primary_key=True, unique=True, default=uuid4)
    )
    created_at: datetime = Field(sa_column=Column(pg.TIMESTAMP, default=datetime.now))
    updated_at: datetime = Field(sa_column=Column(pg.TIMESTAMP, default=datetime.now))
    deleted_at: datetime = Field(sa_column=Column(pg.TIMESTAMP, default=None, nullable=True))
    email: str = Field(index=True, unique=True)
    password: str
    ocupation: str
    is_active: bool = Field(default=True)
    group_id: UUID | None = Field(
        default=None,
        foreign_key="Groups.id"
    )
    group: Group | None = Relationship(back_populates="users")
    gender: str
    education: str
    institution: str
    age: str
    user: str
    password_changed_at: datetime | None = Field(
        sa_column=Column(pg.TIMESTAMP(timezone=True), nullable=True, default=None)
    )


class UserListResponse(SQLModel, table=False):

    """
    This class represents a list of users in database
    """

    id: UUID = Field(
        sa_column=Column(pg.UUID, primary_key=True, unique=True, default=uuid4)
    )
    user: str

    class Config:
        from_attributes = True


class AnonymousUser(SQLModel, table=True):

    """
    This class represents an anonymous user
    """

    __tablename__ = "AnonymousUser"

    id: UUID = Field(
        sa_column=Column(pg.UUID, primary_key=True, unique=True, default=uuid4)
    )
    ocupation: str
    group_id: UUID | None = Field(
        default=None,
        foreign_key="Groups.id"
    )
    group: Group | None = Relationship(back_populates="anonymous_users")


class LogsEmail(SQLModel, table=True):

    """
    This class represents a log email in database
    """

    __tablename__ = "Logs_Email"

    id: UUID = Field(
        sa_column=Column(pg.UUID, primary_key=True, unique=True, default=uuid4)
    )
    created_at: datetime = Field(sa_column=Column(pg.TIMESTAMP, default=datetime.now))
    updated_at: datetime = Field(sa_column=Column(pg.TIMESTAMP, default=datetime.now))
    deleted_at: datetime = Field(sa_column=Column(pg.TIMESTAMP, default=None, nullable=True))
    content: str
    to: str
    sender: str
    subject: str
    has_error: bool = Field(default=False)
    error_message: str | None = Field(default=None)


class PdfFile(SQLModel, table=True):

    """
    This class represents a PDF file in database
    """

    __tablename__ = "PDF_Files"

    id: UUID = Field(
        sa_column=Column(pg.UUID, primary_key=True, unique=True, default=uuid4)
    )
    created_at: datetime = Field(sa_column=Column(pg.TIMESTAMP, default=datetime.now))
    updated_at: datetime = Field(sa_column=Column(pg.TIMESTAMP, default=datetime.now))
    deleted_at: datetime = Field(sa_column=Column(pg.TIMESTAMP, default=None, nullable=True))
    name: str
    path: str
    category: str
    sub_category: str


class Video(SQLModel, table=True):

    """
    This class represents a video in database
    """

    __tablename__ = "Videos"

    id: UUID = Field(
        sa_column=Column(pg.UUID, primary_key=True, unique=True, default=uuid4)
    )
    created_at: datetime = Field(sa_column=Column(pg.TIMESTAMP, default=datetime.now))
    updated_at: datetime = Field(sa_column=Column(pg.TIMESTAMP, default=datetime.now))
    deleted_at: datetime = Field(sa_column=Column(pg.TIMESTAMP, default=None, nullable=True))
    name: str
    path: str
    category: str
    sub_category: str


class Feedback(SQLModel, table=True):

    """
    This class represents a PDF file in database
    """

    __tablename__ = "Feedback"

    id: UUID = Field(
        sa_column=Column(pg.UUID, primary_key=True, unique=True, default=uuid4)
    )
    created_at: datetime = Field(sa_column=Column(pg.TIMESTAMP, default=datetime.now))
    updated_at: datetime = Field(sa_column=Column(pg.TIMESTAMP, default=datetime.now))
    deleted_at: datetime = Field(sa_column=Column(pg.TIMESTAMP, default=None, nullable=True))
    name: str | None = None
    email: str | None = None
    message: str | None = None
    platform_rate: int | None = None
    intuitivity: int | None = None
    type: str


class Geodata(SQLModel, table=True):

    """
    This class represents a Geodata in database
    """

    __tablename__ = "Geodata"

    id: UUID = Field(
        sa_column=Column(pg.UUID, primary_key=True, unique=True, default=uuid4)
    )
    created_at: datetime = Field(sa_column=Column(pg.TIMESTAMP, default=datetime.now))
    updated_at: datetime = Field(sa_column=Column(pg.TIMESTAMP, default=datetime.now))
    deleted_at: datetime = Field(sa_column=Column(pg.TIMESTAMP, default=None, nullable=True))
    cd_sedec: str
    name: str
    category: str
    sub_category: str
    description: str
    origin_name: str
    url_acess: str
    geotype: str


class GeoJsonData(SQLModel, table=True):

    __tablename__ = "GeoJsonData"

    id: UUID = Field(
        sa_column=Column(pg.UUID, primary_key=True, unique=True, default=uuid4)
    )
    name: str
    data: dict = Field(sa_column=Column(pg.JSON))


class PasswordResetToken(SQLModel, table=True):

    """
    Single-use token for password recovery. The raw token is emailed to the
    user as part of a reset link; only the SHA-256 hash is persisted here.
    """

    __tablename__ = "password_reset_token"

    id: UUID = Field(
        sa_column=Column(pg.UUID, primary_key=True, unique=True, default=uuid4)
    )
    user_id: UUID = Field(foreign_key="Users.id")
    token_hash: str = Field(index=True)
    expires_at: datetime = Field(sa_column=Column(pg.TIMESTAMP(timezone=True), nullable=False))
    used: bool = Field(default=False)
    created_at: datetime = Field(sa_column=Column(pg.TIMESTAMP, default=datetime.now))


class DataStation(SQLModel, table=True):
    __tablename__ = 'data_station'
    id: UUID = Field( sa_column=Column(pg.UUID, primary_key=True, unique=True, default=uuid4))
    name: str = Field(index=True, unique=True, nullable=False)
    sensor_height: float | None = Field(default=None) # Altura do sensor em metros
    type: UUID = Field(foreign_key="station_type.id", index=True, nullable=False)
    layer_id: UUID | None = Field(default=None, foreign_key="Layer.id", index=True)
    station_type_ref: Optional["StationType"] = Relationship(back_populates="stations")
    lidar_data: list["LidarStationData"] = Relationship(back_populates="station")
    solarimetric_data: list["SolarimetricStationData"] = Relationship(back_populates="station")

class StationType(SQLModel, table=True):
    __tablename__ = 'station_type'
    id: UUID = Field( sa_column=Column(pg.UUID, primary_key=True, unique=True, default=uuid4))
    name: str = Field(index=True, unique=True, nullable=False)
    stations: list["DataStation"] = Relationship(back_populates="station_type_ref")


class LidarStationData(SQLModel, table=True):
    __tablename__ = 'lidar_station_data'
    id: UUID = Field( sa_column=Column(pg.UUID, primary_key=True, unique=True, default=uuid4) ) # id: int | None = Field(default=None, primary_key=True)
    dt: datetime = Field(index=True)    #Time and Date
    m_temp  : float =  Field()          # Met Air Temperature  # Temperatura do ar
    m_pres : float =  Field()           # Met Pressure # Pressão
    m_wspd: float =  Field()            # Met Wind Speed # Velocidade do vento
    m_wdir: float =  Field()            # Met Wind Direction # Direção do Vento
    height: int =  Field(index=True)    # Height (m) #ALTURA em M
    h_spd: float =  Field(index=True)   # Horizontal Wind Speed #Velocidade média do Vento Horizontal
    ti : float =  Field()               # Turbulence Intensity # Intensidade da turbulência
    wdir: float =  Field(index=True)    # Wind Direction # Direção do Vento

    station_id: UUID = Field(foreign_key="data_station.id", index=True, nullable=False)
    __table_args__ = ( UniqueConstraint("dt", "station_id", "height", name="uq_lidar_station_data_datetime_station_id_height"), )
    station: DataStation = Relationship(back_populates="lidar_data")


class SolarimetricStationData(SQLModel, table=True):
    __tablename__ = 'solarimetric_stations'
    id: UUID = Field( sa_column=Column(pg.UUID, primary_key=True, unique=True, default=uuid4) ) # id: int | None = Field(default=None, primary_key=True)
    dt: datetime = Field(index=True)    #Time and Date
    ghi  : float =  Field()             # Global Horizontal Irradiance  # Irradiância Global Horizontal
    hum : float =  Field()              # Met humidity # Umidade
    temp: float =  Field()              # Met temperature # Temperatura
    vel: float =  Field()               # Met Wind Speed # Velocidade do Vento

    station_id: UUID = Field(foreign_key="data_station.id", index=True, nullable=False)
    __table_args__ = ( UniqueConstraint("dt", "station_id", name="uq_solarimetric_stations_datetime_station_id"), )
    station: DataStation = Relationship(back_populates="solarimetric_data")


SolarStationData = SolarimetricStationData


class AdminAnalyticsEvent(SQLModel, table=True):
    __tablename__ = "admin_analytics_event"

    id: UUID = Field(
        sa_column=Column(pg.UUID, primary_key=True, unique=True, default=uuid4)
    )
    created_at: datetime = Field(sa_column=Column(pg.TIMESTAMP, default=datetime.utcnow))
    updated_at: datetime = Field(sa_column=Column(pg.TIMESTAMP, default=datetime.utcnow))
    deleted_at: datetime = Field(sa_column=Column(pg.TIMESTAMP, default=None, nullable=True))

    domain: str = Field(index=True)
    event_type: str = Field(index=True)
    label: str
    occurred_at: datetime = Field(index=True)
    actor_user_id: UUID | None = Field(default=None, foreign_key="Users.id", index=True)
    actor_name: str | None = Field(default=None)
    target_type: str | None = Field(default=None, index=True)
    target_id: str | None = Field(default=None, index=True)
    status: str | None = Field(default=None, index=True)
    endpoint_key: str | None = Field(default=None, index=True)
    method: str | None = Field(default=None)
    status_code: int | None = Field(default=None, index=True)
    latency_ms: int | None = Field(default=None)
    file_id: UUID | None = Field(default=None, foreign_key="PDF_Files.id", index=True)
    layer_id: UUID | None = Field(default=None, foreign_key="Layer.id", index=True)
    payload: dict | None = Field(default=None, sa_column=Column("metadata", pg.JSON, nullable=True))


class AdminAnalyticsExport(SQLModel, table=True):
    __tablename__ = "admin_analytics_export"

    id: UUID = Field(
        sa_column=Column(pg.UUID, primary_key=True, unique=True, default=uuid4)
    )
    created_at: datetime = Field(sa_column=Column(pg.TIMESTAMP, default=datetime.utcnow))
    updated_at: datetime = Field(sa_column=Column(pg.TIMESTAMP, default=datetime.utcnow))
    deleted_at: datetime = Field(sa_column=Column(pg.TIMESTAMP, default=None, nullable=True))

    domain: str
    format: str
    status: str
    name: str
    path: str
    content_type: str
    generated_at: datetime | None = Field(sa_column=Column(pg.TIMESTAMP, default=None, nullable=True))
    expires_at: datetime | None = Field(sa_column=Column(pg.TIMESTAMP, default=None, nullable=True))
    detail: str | None = Field(default=None)
    filters: dict | None = Field(default=None, sa_column=Column(pg.JSON, nullable=True))
    columns: list | None = Field(default=None, sa_column=Column(pg.JSON, nullable=True))
