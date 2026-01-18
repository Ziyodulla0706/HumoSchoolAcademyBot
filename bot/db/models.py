from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, UniqueConstraint, Float, Text, Date
from sqlalchemy.sql import func
from bot.db.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, nullable=False)
    full_name = Column(String, nullable=False)
    phone = Column(String, nullable=True)
    role = Column(String, default="parent")  # parent / admin / teacher
    is_verified = Column(Boolean, default=False)
    is_blocked = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())


class Child(Base):
    __tablename__ = "children"

    id = Column(Integer, primary_key=True)
    parent_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    full_name = Column(String, nullable=False)
    class_name = Column(String, nullable=False)
    created_at = Column(DateTime, server_default=func.now())


class PickupRequest(Base):
    __tablename__ = "pickup_requests"

    id = Column(Integer, primary_key=True)
    parent_id = Column(Integer, ForeignKey("users.id"))
    child_id = Column(Integer, ForeignKey("children.id"))
    arrival_minutes = Column(Integer)
    status = Column(String, default="ACTIVE")  # ACTIVE / DONE / EXPIRED
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, nullable=True)


class Subject(Base):
    __tablename__ = "subjects"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False, unique=True)  # Математика, Русский язык и т.д.
    created_at = Column(DateTime, server_default=func.now())


class Teacher(Base):
    __tablename__ = "teachers"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=True)  # Предмет, который ведёт
    status = Column(String, default="pending")  # pending / approved
    is_verified = Column(Boolean, default=False)  # для обратной совместимости
    created_at = Column(DateTime, server_default=func.now())


class TeacherClass(Base):
    __tablename__ = "teacher_classes"

    id = Column(Integer, primary_key=True)
    teacher_id = Column(Integer, ForeignKey("teachers.id"), nullable=False)
    class_name = Column(String, nullable=False)

    __table_args__ = (
        UniqueConstraint("teacher_id", "class_name", name="uq_teacher_class"),
    )


class Attendance(Base):
    __tablename__ = "attendance"

    id = Column(Integer, primary_key=True)
    child_id = Column(Integer, ForeignKey("children.id"), nullable=False)
    teacher_id = Column(Integer, ForeignKey("teachers.id"), nullable=False)
    date = Column(Date, nullable=False)
    status = Column(String, nullable=False)  # present / absent / late
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("child_id", "date", name="uq_attendance_child_date"),
    )


class Grade(Base):
    __tablename__ = "grades"

    id = Column(Integer, primary_key=True)
    child_id = Column(Integer, ForeignKey("children.id"), nullable=False)
    teacher_id = Column(Integer, ForeignKey("teachers.id"), nullable=False)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False)
    grade = Column(Integer, nullable=False)  # 2, 3, 4, 5
    comment = Column(String, nullable=True)
    date = Column(Date, nullable=False, server_default=func.now())
    created_at = Column(DateTime, server_default=func.now())


class Comment(Base):
    __tablename__ = "comments"

    id = Column(Integer, primary_key=True)
    child_id = Column(Integer, ForeignKey("children.id"), nullable=False)
    teacher_id = Column(Integer, ForeignKey("teachers.id"), nullable=False)
    comment_type = Column(String, nullable=False)  # behavior / performance / discipline
    text = Column(Text, nullable=False)
    created_at = Column(DateTime, server_default=func.now())


class Homework(Base):
    __tablename__ = "homework"

    id = Column(Integer, primary_key=True)
    teacher_id = Column(Integer, ForeignKey("teachers.id"), nullable=False)
    class_name = Column(String, nullable=False)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False)
    text = Column(Text, nullable=False)
    due_date = Column(Date, nullable=False)
    created_at = Column(DateTime, server_default=func.now())






