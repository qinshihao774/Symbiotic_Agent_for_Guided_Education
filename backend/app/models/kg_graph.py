"""KgGraph SQLAlchemy ORM 模型"""

from sqlalchemy import BigInteger, Column, DateTime, Integer, String, func

from app.core.database import Base


class KgGraph(Base):
    """知识图谱元数据表"""

    __tablename__ = "kg_graphs"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    graph_name = Column(String(128), nullable=False, unique=True)
    original_filename = Column(String(256), nullable=False)
    file_path = Column(String(512))
    course_id = Column(BigInteger, nullable=True, index=True)
    node_count = Column(Integer, default=0)
    edge_count = Column(Integer, default=0)
    chunk_count = Column(Integer, default=0)
    status = Column(String(20), default="pending")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
