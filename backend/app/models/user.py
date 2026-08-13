"""Student 和 Teacher SQLAlchemy ORM 模型"""
from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, String, func
from app.core.database import Base


class Student(Base):
    __tablename__ = "students"

    stu_id = Column(BigInteger, primary_key=True, autoincrement=True)
    stu_name = Column(String(64), nullable=False)
    stu_gender = Column(String(4), nullable=True)
    stu_email = Column(String(128), nullable=True, unique=True)
    stu_pwd = Column(String(256), nullable=True)
    stu_level = Column(String(32), nullable=True)
    class_id = Column(BigInteger, ForeignKey("classes.class_id"), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class Teacher(Base):
    __tablename__ = "teachers"

    tea_id = Column(BigInteger, primary_key=True, autoincrement=True)
    tea_name = Column(String(64), nullable=False)
    tea_email = Column(String(128), nullable=True, unique=True)
    tea_pwd = Column(String(256), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
