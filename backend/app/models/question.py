"""Question SQLAlchemy ORM 模型"""
from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, SmallInteger, String, Text, func, Index, CheckConstraint
from sqlalchemy.dialects.postgresql import JSON
from app.core.database import Base


class Question(Base):
    __tablename__ = "questions"

    question_id = Column(BigInteger, primary_key=True, autoincrement=True)
    question_description = Column(Text, nullable=False)
    question_answer = Column(Text, nullable=False)
    question_options = Column(JSON, nullable=True)
    question_type = Column(String(32), nullable=False)
    question_difficulty = Column(SmallInteger, nullable=False)
    question_explanation = Column(Text, nullable=True)
    course_id = Column(BigInteger, ForeignKey("courses.course_id"), nullable=False, index=True)
    kg_id = Column(BigInteger, ForeignKey("kg_graphs.id"), nullable=True, index=True)
    kg_node_name = Column(String(128), nullable=True, index=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("ix_questions_difficulty", "question_difficulty"),
        CheckConstraint(
            "question_difficulty >= 1 AND question_difficulty <= 5",
            name="ck_question_difficulty_range",
        ),
    )
