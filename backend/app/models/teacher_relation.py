"""TeacherCourse / TeacherClass SQLAlchemy ORM 模型"""
from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, func, Index
from app.core.database import Base


class TeacherCourse(Base):
    """教师-学科关系表"""
    __tablename__ = "teacher_course"

    tea_id = Column(BigInteger, ForeignKey("teachers.tea_id"), primary_key=True)
    course_id = Column(BigInteger, ForeignKey("courses.course_id"), primary_key=True)
    created_at = Column(DateTime, server_default=func.now())


class TeacherClass(Base):
    """教师-班级关系表"""
    __tablename__ = "teacher_class"

    class_id = Column(BigInteger, ForeignKey("classes.class_id"), primary_key=True)
    tea_id = Column(BigInteger, ForeignKey("teachers.tea_id"), primary_key=True)
    created_at = Column(DateTime, server_default=func.now())
    __table_args__ = (
        Index("ix_teacher_class_tea_id", "tea_id"),
    )
