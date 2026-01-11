from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime
from sqlalchemy.sql import func
from bot.db.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, nullable=False)
    full_name = Column(String, nullable=False)
    phone = Column(String, nullable=True)
    role = Column(String, default="parent")  # parent / admin
    is_verified = Column(Boolean, default=False)
    is_blocked = Column(Boolean, default=False)  # добавили поле
    created_at = Column(DateTime, server_default=func.now())


class Child(Base):
    __tablename__ = "children"

    id = Column(Integer, primary_key=True)
    parent_id = Column(Integer, ForeignKey("users.id"))
    full_name = Column(String, nullable=False)
    class_name = Column(String, nullable=False)


class PickupRequest(Base):
    __tablename__ = "pickup_requests"

    id = Column(Integer, primary_key=True)
    parent_id = Column(Integer, ForeignKey("users.id"))
    child_id = Column(Integer, ForeignKey("children.id"))
    arrival_minutes = Column(Integer)
    status = Column(String, default="ACTIVE")  # ACTIVE / DONE
    created_at = Column(DateTime, server_default=func.now())







