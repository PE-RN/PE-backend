from datetime import datetime
from uuid import UUID, uuid4

import sqlalchemy.dialects.postgresql as pg
from sqlmodel import Column, Field, SQLModel, Relationship


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
