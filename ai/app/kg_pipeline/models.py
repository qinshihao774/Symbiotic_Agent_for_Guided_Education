"""知识图谱构建 Pipeline 的数据模型"""

from __future__ import annotations

import re
import uuid
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class EntityType(str, Enum):
    """预定义的计算机学科核心实体类型

    只保留 6 种核心类型（LLM 可产出）+ Chapter（仅规则生成）+ TERM（噪声桶）。
    被删除的低价值类型（Operation/Method/Process/Function/Standard/Tool/Model）
    不再提取；Model 并入 Technology。
    """
    CHAPTER = "Chapter"           # 章（仅由 ChapterBuilder 规则生成，LLM 禁止产出）
    CONCEPT = "Concept"
    ALGORITHM = "Algorithm"
    DATA_STRUCTURE = "DataStructure"
    PROTOCOL = "Protocol"
    PRINCIPLE = "Principle"
    TECHNOLOGY = "Technology"     # 技术/系统/模型（原 Technology + Model）
    TERM = "Term"                 # 噪声/未知类型桶：LLM 不应产出，剪枝白名单丢弃

    @classmethod
    def _missing_(cls, value):
        """未知类型降级：先查别名映射（中文/英文变体），命中则返回对应类型；
        否则降级为 TERM（噪声桶），不中断流水线，由剪枝阶段丢弃"""
        logger = __import__("logging").getLogger(__name__)
        if isinstance(value, str):
            hit = _TYPE_LOOKUP.get(_normalize_type_key(value))
            if hit is not None:
                return hit
        logger.warning(f"[KG] Unknown entity type '{value}', falling back to 'Term'")
        return cls.TERM


# ---------------------------------------------------------------------------
# 类型别名映射 — 处理 LLM 返回中文名 / 英文大小写·空白·下划线变体
# ---------------------------------------------------------------------------


def _normalize_type_key(value: str) -> str:
    """归一化类型字符串：去首尾空白、转小写、去空白/下划线/连字符

    'DataStructure' / 'Data Structure' / 'data_structure' → 'datastructure'
    """
    return re.sub(r"[\s\-_]", "", value.strip().lower())


# 中文别名 → 规范类型（低价值类型映射到 TERM，由剪枝白名单丢弃）
_TYPE_ALIASES: dict[str, EntityType] = {
    "概念": EntityType.CONCEPT,
    "算法": EntityType.ALGORITHM,
    "数据结构": EntityType.DATA_STRUCTURE,
    "协议": EntityType.PROTOCOL,
    "原理": EntityType.PRINCIPLE,
    "原理/定理": EntityType.PRINCIPLE,
    "技术": EntityType.TECHNOLOGY,
    "技术/系统/模型": EntityType.TECHNOLOGY,
    "模型": EntityType.TECHNOLOGY,          # Model 并入 Technology
    # 低价值类型 → TERM 噪声桶
    "术语": EntityType.TERM,
    "函数": EntityType.TERM,
    "操作": EntityType.TERM,
    "方法": EntityType.TERM,
    "流程": EntityType.TERM,
    "工具": EntityType.TERM,
    "标准": EntityType.TERM,
}

# 规范英文值（大小写/空白/下划线变体）+ 中文别名 → EntityType 的查找表
_TYPE_LOOKUP: dict[str, EntityType] = {
    _normalize_type_key(member.value): member for member in EntityType
}
for _alias, _member in _TYPE_ALIASES.items():
    _TYPE_LOOKUP.setdefault(_normalize_type_key(_alias), _member)


class KGNode(BaseModel):
    """知识图谱节点 — 对应 AGE 中的一个 Vertex"""
    id: str
    name: str = ""
    type: EntityType
    description: str = ""
    source_chunk_index: Optional[int] = None

    def __init__(self, **data):
        if not data.get("name"):
            data["name"] = data.get("id", "")
        super().__init__(**data)


class KGEdge(BaseModel):
    """知识图谱边 — 对应 AGE 中的一条 Edge"""
    source_node_id: str
    target_node_id: str
    relationship_name: str
    description: Optional[str] = None


class KnowledgeGraph3D(BaseModel):
    """单个切片的知识图谱"""
    nodes: list[KGNode] = Field(default_factory=list)
    edges: list[KGEdge] = Field(default_factory=list)


class DocumentChunk(BaseModel):
    """文档切片"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    text: str
    chunk_index: int = 0
    chunk_size: int = 0
    heading_path: list[str] = []      # 如 ["第3章 栈和队列", "3.1 栈"]
    heading_levels: list[int] = []    # 如 [2, 3]


class PipelineResult(BaseModel):
    """Pipeline 执行结果统计"""
    chunks: int = 0
    nodes: int = 0
    edges: int = 0
    status: str = "pending"
    error: Optional[str] = None
    failed_chunks: int = 0
