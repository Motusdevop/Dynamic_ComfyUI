from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)

    instances = relationship("Instance", back_populates="user", cascade="all, delete-orphan")


class Instance(Base):
    __tablename__ = "instances"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    container_id: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    port: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="running")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("User", back_populates="instances")


class SharedModel(Base):
    __tablename__ = "shared_models"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    url: Mapped[str] = mapped_column(String(2048), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="downloading")
