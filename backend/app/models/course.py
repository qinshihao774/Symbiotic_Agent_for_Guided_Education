"""Course SQLAlchemy ORM 模型"""
from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, String, Text, func
from app.core.database import Base


class Course(Base):
    __tablename__ = "courses"

    course_id = Column(BigInteger, primary_key=True, autoincrement=True)
    course_name = Column(String(64), nullable=False, unique=True)
    course_description = Column(Text, nullable=True)
    kg_id = Column(BigInteger, ForeignKey("kg_graphs.id"), nullable=True, unique=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
