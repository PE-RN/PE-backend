from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, DateTime
from .database import Base
from datetime import datetime


class User(Base):

    __tablename__ = "Users"

    id = Column(Integer, primary_key=True)
    created_at = Column(DateTime, default=datetime.datetime)
    updated_at = Column(DateTime, default=datetime.datetime, onupdate=datetime.datetime)
    deleted_at = Column(DateTime, default=None, onupdate=datetime.datetime)
    password = Column(String)
    ocupation = Column(String)
    is_active = Column(Boolean, default=False)
    group_id = Column(Integer, ForeignKey("groups.id"))


class Groups(Base):

    __tablename__ = "Groups"
    id = Column(Integer, primary_key=True)
    created_at = Column(DateTime, default=datetime.datetime)
    updated_at = Column(DateTime, default=datetime.datetime, onupdate=datetime.datetime)
    deleted_at = Column(DateTime, default=None, onupdate=datetime.datetime)
    name = Column(String)
    description = Column(String)


class LogsEmail(Base):
    __tablename__ = "Logs_Email"

    id = Column(Integer, primary_key=True)
    created_at = Column(DateTime, default=datetime.datetime)
    updated_at = Column(DateTime, default=datetime.datetime, onupdate=datetime.datetime)
    deleted_at = Column(DateTime, default=None, onupdate=datetime.datetime)


class PdfFile(Base):

    __tablename__ = "PDF_Files"

    id = Column(Integer, primary_key=True)
    created_at = Column(DateTime, default=datetime.datetime)
    updated_at = Column(DateTime, default=datetime.datetime, onupdate=datetime.datetime)
    deleted_at = Column(DateTime, default=None, onupdate=datetime.datetime)
    name = Column(String)
    path = Column(String)
    category = Column(String)


class Video(Base):

    __tablename__ = "Videos"

    id = Column(Integer, primary_key=True)
    created_at = Column(DateTime, default=datetime.datetime)
    updated_at = Column(DateTime, default=datetime.datetime, onupdate=datetime.datetime)
    deleted_at = Column(DateTime, default=None, onupdate=datetime.datetime)
    name = Column(String)
    path = Column(String)
    category = Column(String)


class Geodata(Base):

    __tablename__ = "Geodata"

    id = Column(Integer, primary_key=True)
    created_at = Column(DateTime, default=datetime.datetime)
    updated_at = Column(DateTime, default=datetime.datetime, onupdate=datetime.datetime)
    deleted_at = Column(DateTime, default=None, onupdate=datetime.datetime)
    cd_sedec = Column(String)
    name = Column(String)
    category = Column(String)
    sub_category = Column(String)
    description = Column(String)
    origin_name = Column(String)
    url_acess = Column(String)
