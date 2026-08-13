"""ExerciseRecord SQLAlchemy ORM 模型"""
from sqlalchemy import BigInteger, Boolean, Column, DateTime, Float, ForeignKey, SmallInteger, String, Text, func, Index, CheckConstraint
from app.core.database import Base


class ExerciseRecord(Base):
    __tablename__ = "exercise_records"
    do_id = Column(BigInteger, primary_key=True, autoincrement=True)
    question_id = Column(BigInteger, ForeignKey("questions.question_id"), nullable=False, index=True)
    stu_id = Column(BigInteger, ForeignKey("students.stu_id"), nullable=False, index=True)
    kg_id = Column(BigInteger, ForeignKey("kg_graphs.id"), nullable=True)
    course_id = Column(BigInteger, ForeignKey("courses.course_id"), nullable=True)
    kg_node_name = Column(String(128), nullable=True, index=True)
    question_type = Column(String(32), nullable=True)
    question_difficulty = Column(SmallInteger, nullable=True)
    do_stu_answer = Column(Text, nullable=False)
    do_score = Column(Float, nullable=True)
    do_isTrue = Column("do_istrue", Boolean, nullable=True)
    iserror_firstly = Column(Boolean, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    __table_args__ = (
        Index("ix_exercise_records_stu_node", "stu_id", "kg_node_name"),
        Index("ix_exercise_records_course_id", "course_id"),
        Index("ix_exercise_records_kg_id", "kg_id"),
        CheckConstraint("do_score >= 0.0 AND do_score <= 10.0", name="ck_do_score_range"),
        CheckConstraint(
            "question_difficulty >= 1 AND question_difficulty <= 5",
            name="ck_exercise_question_difficulty",
        ),
    )
