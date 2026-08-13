"""Learning SQLAlchemy ORM 模型 — 学生掌握度"""
from sqlalchemy import BigInteger, Column, DateTime, Float, ForeignKey, Integer, String, func, CheckConstraint, Index
from app.core.database import Base


class StudentCourseMastery(Base):
    __tablename__ = "student_course_mastery"

    stu_id = Column(BigInteger, ForeignKey("students.stu_id"), primary_key=True)
    course_id = Column(BigInteger, ForeignKey("courses.course_id"), primary_key=True)
    course_degree = Column(Float, nullable=False)
    course_process = Column(Float, nullable=True)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        CheckConstraint(
            "course_degree >= 0.0 AND course_degree <= 5.0",
            name="ck_course_degree_range",
        ),
        CheckConstraint(
            "course_process >= 0.0 AND course_process <= 1.0",
            name="ck_course_process_range",
        ),
    )


class StudentKnowledgeMastery(Base):
    __tablename__ = "student_knowledge_mastery"

    stu_id = Column(BigInteger, ForeignKey("students.stu_id"), primary_key=True)
    course_id = Column(BigInteger, ForeignKey("courses.course_id"), primary_key=True)
    kg_node_name = Column(String(128), primary_key=True)
    kg_id = Column(BigInteger, ForeignKey("kg_graphs.id"), nullable=True)
    kg_degree = Column(Float, nullable=False)
    answered_count = Column(Integer, default=0)
    correct_count = Column(Integer, default=0)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        CheckConstraint(
            "kg_degree >= 0.0 AND kg_degree <= 5.0",
            name="ck_kg_degree_range",
        ),
        Index("ix_student_knowledge_mastery_node_name", "kg_node_name"),
        Index("ix_student_knowledge_mastery_course", "course_id"),
        Index("ix_student_knowledge_mastery_kg_id", "kg_id"),
    )
