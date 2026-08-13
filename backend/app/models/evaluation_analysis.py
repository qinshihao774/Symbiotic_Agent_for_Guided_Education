"""EvaluationAnalysis SQLAlchemy ORM 模型 — 评价分析表"""
from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Index, String, Text, func
from app.core.database import Base


class EvaluationAnalysis(Base):
    __tablename__ = "evaluation_analysis"

    ea_id = Column(BigInteger, primary_key=True, autoincrement=True)
    stu_id = Column(BigInteger, ForeignKey("students.stu_id"), nullable=False)
    # 发布者 ID：老师为 tea_id，AI 为 null
    publisher_id = Column(BigInteger, nullable=True)
    # 发布者名称：老师为 tea_name，AI 为 "AI"
    publisher_name = Column(String(64), nullable=False)
    ea_description = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("ix_evaluation_analysis_stu_id", "stu_id"),
        Index("ix_evaluation_analysis_publisher_id", "publisher_id"),
    )
