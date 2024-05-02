from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, DateTime
from sqlalchemy.orm import relationship
from .database import Base
from datetime import datetime


class Groups(Base):

    __tablename__ = "Groups"
    id = Column(Integer, primary_key=True)
    created_at = Column(DateTime, default=datetime.now())
    updated_at = Column(DateTime, default=datetime.now(), onupdate=datetime.now())
    deleted_at = Column(DateTime, default=None)
    name = Column(String)
    description = Column(String)

    users = relationship("Users", back_populates="groups")


class User(Base):

    __tablename__ = "Users"

    id = Column(Integer, primary_key=True)
    created_at = Column(DateTime, default=datetime.now())
    updated_at = Column(DateTime, default=datetime.now(), onupdate=datetime.now())
    deleted_at = Column(DateTime, default=None)
    email = Column(String)
    password = Column(String)
    ocupation = Column(String)
    is_active = Column(Boolean, default=False)
    group_id = Column(Integer, ForeignKey("Groups.id"))

    groups = relationship("Groups", back_populates="users")


class LogsEmail(Base):
    __tablename__ = "Logs_Email"

    id = Column(Integer, primary_key=True)
    created_at = Column(DateTime, default=datetime.now())
    updated_at = Column(DateTime, default=datetime.now(), onupdate=datetime.now())
    deleted_at = Column(DateTime, default=None)


class PdfFile(Base):

    __tablename__ = "PDF_Files"

    id = Column(Integer, primary_key=True)
    created_at = Column(DateTime, default=datetime.now())
    updated_at = Column(DateTime, default=datetime.now(), onupdate=datetime.now())
    deleted_at = Column(DateTime, default=None)
    name = Column(String)
    path = Column(String)
    category = Column(String)


class Video(Base):

    __tablename__ = "Videos"

    id = Column(Integer, primary_key=True)
    created_at = Column(DateTime, default=datetime.now())
    updated_at = Column(DateTime, default=datetime.now(), onupdate=datetime.now())
    deleted_at = Column(DateTime, default=None)
    name = Column(String)
    path = Column(String)
    category = Column(String)


class Geodata(Base):

    __tablename__ = "Geodata"

    id = Column(Integer, primary_key=True)
    created_at = Column(DateTime, default=datetime.now())
    updated_at = Column(DateTime, default=datetime.now(), onupdate=datetime.now())
    deleted_at = Column(DateTime, default=None)
    cd_sedec = Column(String)
    name = Column(String)
    category = Column(String)
    sub_category = Column(String)
    description = Column(String)
    origin_name = Column(String)
    url_acess = Column(String)
    package = Column(String)
    geotype = Column(String)
