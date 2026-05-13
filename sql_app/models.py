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
        default='5c190872-1800-4c8c-9411-23937d0a8d52',
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
        default='5c190872-1800-4c8c-9411-23937d0a8d52',
        foreign_key="Groups.id"
    )
    group: Group | None = Relationship(back_populates="users")
    gender: str
    education: str
    institution: str
    age: str
    user: str


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

class Platform(SQLModel, table=True):
    __tablename__ = 'platform'
    id: UUID = Field( sa_column=Column(pg.UUID, primary_key=True, unique=True, default=uuid4))
    name: str = Field(index=True, unique=True, nullable=False)
    # latitude: float= Field()
    # longitude: float = Field()
    sensor_height: float| None = Field() # Altura do sensor em metros
    
    # Um sensor pode ter vários dados
    qualified_data: list["QualifiedData"] = Relationship(back_populates="platform")

class QualifiedData(SQLModel, table=True):
    __tablename__ = 'qualified_data'
    id: UUID = Field( sa_column=Column(pg.UUID, primary_key=True, unique=True, default=uuid4) )# id: int | None = Field(default=None, primary_key=True)
    dt: datetime = Field(index=True) #Time and Date
    m_temp  : float =  Field()  # Met Air Temperature  # Temperatura do ar
    m_pres : float =  Field()  # Met Pressure # Pressão
    m_wspd: float =  Field() # Met Wind Speed # Velocidade do vento
    m_wdir: float =  Field()#Met Wind Direction # Direção do Vento

    height: int =  Field(index=True)  # Height (m) #ALTURA em M
    h_spd: float =  Field(index=True) # Horizontal Wind Speed #Velocidade média do Vento Horizontal
    ti : float =  Field() # Turbulence Intensity # Intensidade da turbulência
    wdir: float =  Field(index=True)# Wind Direction # Direção do Vento

    plat_id: UUID = Field(foreign_key="platform.id", index=True, nullable=False)
    __table_args__ = ( UniqueConstraint("dt", "plat_id", "height", name="uq_qualified_data_datetime_plat_id_height"), )
    platform: Platform = Relationship(back_populates="qualified_data")