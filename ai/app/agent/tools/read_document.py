"""文档读取工具 — 基于 pgvector + GraphRAG 的 RAG 查询"""

import logging

from app.agent.context import current_kg_graph_ids
from app.agent.tool_registry import ToolRegistry
from app.engines.rag.pipeline import RagPipeline, DetailLevel

logger = logging.getLogger(__name__)


@ToolRegistry.register(
    name="read_document",
    description="""读取学生上传的课件、笔记、教材内容。
当用户询问特定课程/章节的知识点时使用。
支持三种详细程度，通过 detail_level 控制：
- text: 仅返回相关文本片段
- entities: 返回文本 + 涉及的知识点实体名
- subgraph: 返回文本 + 实体 + 知识点章节路径""",
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "检索关键词，如'虚存管理'、'数据库范式'等",
            },
            "top_k": {
                "type": "integer",
                "description": "返回的最大文档片段数，默认5",
            },
            "detail_level": {
                "type": "string",
                "enum": ["text", "entities", "subgraph"],
                "description": "详细程度：text=仅文本(默认), entities=文本+实体, subgraph=文本+实体+章节路径",
            },
            "course_id": {
                "type": "integer",
                "description": "按课程过滤（可选，传入课程ID）",
            },
        },
        "required": ["query"],
    },
)
async def read_document(
    user_id: int,
    query: str,
    top_k: int = 5,
    detail_level: str = "text",
    course_id: int | None = None,
) -> str:
    """从 pgvector 检索文档片段，经 GraphRAG 排序后返回"""
    try:
        kg_graph_ids = current_kg_graph_ids.get()

        pipeline = RagPipeline()
        return await pipeline.run(
            query=query,
            top_k=top_k,
            detail_level=DetailLevel(detail_level),
            course_id=course_id,
            kg_graph_ids=kg_graph_ids if kg_graph_ids else None,
        )
    except Exception as e:
        logger.error(f"Document query failed: {e}")
        return f"文档检索失败: {str(e)}。请检查数据库连接或稍后重试。"
