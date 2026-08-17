"""Class SQLAlchemy ORM 模型"""
from sqlalchemy import BigInteger, Column, DateTime, Float, Integer, String, Text, func
from app.core.database import Base


class Class(Base):
    __tablename__ = "classes"

    class_id = Column(BigInteger, primary_key=True, autoincrement=True)
    class_name = Column(String(64), nullable=False, unique=True)
    classmates_num = Column(Integer, nullable=True, default=0)
    ai_level = Column(String(32), nullable=True)
    ai_suggestion = Column(Text, nullable=True)
    course_avg_process = Column(Float, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
