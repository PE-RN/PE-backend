from datetime import datetime
from uuid import UUID, uuid4

import sqlalchemy.dialects.postgresql as pg
from sqlmodel import Column, Field, SQLModel


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
        sa_column=Column(pg.UUID),
        default=None,

    )


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
        sa_column=Column(pg.UUID),
        default=None,
    )


class AnonymousUser(SQLModel, table=True):

    """
    This class represents an anonymous user
    """

    __tablename__ = "AnonymousUser"

    id: UUID = Field(
        sa_column=Column(pg.UUID, primary_key=True, unique=True, default=uuid4)
    )
    ocupation: str


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
