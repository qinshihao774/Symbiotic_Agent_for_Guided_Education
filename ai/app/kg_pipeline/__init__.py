from __future__ import annotations

from app.kg_pipeline.models import KGNode, KGEdge, KnowledgeGraph3D, DocumentChunk, EntityType, PipelineResult
from app.kg_pipeline.chunking import MarkdownChunker
from app.kg_pipeline.chapter_builder import ChapterBuilder
from app.kg_pipeline.extraction import KGExtractor
from app.kg_pipeline.graph_builder import GraphBuilder
from app.kg_pipeline.cross_chapter import CrossChapterExtractor
from app.kg_pipeline.storage import AgeStorage

# 延迟导入 pipeline（需要 mineru，仅在远程服务器可用）
def get_pipeline() -> type:
    from app.kg_pipeline.pipeline import KGPipeline  # noqa: F811
    return KGPipeline

__all__ = [
    "KGNode", "KGEdge", "KnowledgeGraph3D", "DocumentChunk", "EntityType", "PipelineResult",
    "MarkdownChunker", "ChapterBuilder", "KGExtractor", "GraphBuilder",
    "CrossChapterExtractor", "AgeStorage",
]
