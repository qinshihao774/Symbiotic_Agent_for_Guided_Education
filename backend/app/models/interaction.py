"""互动消息与互动回答 SQLAlchemy ORM 模型"""
from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Integer, Text, func
from app.core.database import Base


class InteractionMessage(Base):
    """互动消息表 — 学生发布的提问/对话"""
    __tablename__ = "interaction_messages"

    msg_id = Column(BigInteger, primary_key=True, autoincrement=True)
    msg_texts = Column(Text, nullable=False)
    stu_id = Column(BigInteger, ForeignKey("students.stu_id"), nullable=False)
    answer_num = Column(Integer, nullable=True, default=0)
    created_at = Column(DateTime, server_default=func.now())


class InteractionAnswer(Base):
    """互动消息-回答关系表 — 学生或老师对某条消息的回答"""
    __tablename__ = "interaction_answers"

    answer_id = Column(BigInteger, primary_key=True, autoincrement=True)
    answer_text = Column(Text, nullable=False)
    msg_id = Column(BigInteger, ForeignKey("interaction_messages.msg_id"), nullable=False)
    stu_id = Column(BigInteger, ForeignKey("students.stu_id"), nullable=True)
    tea_id = Column(BigInteger, ForeignKey("teachers.tea_id"), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
