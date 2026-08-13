"""文档入库 — 大切片 → 子切片 → embedding → pgvector"""

import json
import logging
from typing import Any

import asyncpg

from app.config import get_pgvector_dsn
from app.engines.rag.embedding import EmbeddingClient

logger = logging.getLogger(__name__)


def _get_first_sentence(text: str) -> str:
    """提取文本的第一句（句号识别）"""
    idx = text.find("。")
    if idx == -1:
        return text
    return text[: idx + 1]


def _get_last_sentence(text: str) -> str:
    """提取文本的最后一句（句号识别）"""
    idx = text.rfind("。")
    if idx == -1:
        return text
    prev = text.rfind("。", 0, idx)
    if prev == -1:
        return text
    return text[prev + 1 :]


def split_sub_chunks(chunk_text: str) -> list[tuple[str, int]]:
    """大切片 → 按段落分割为子切片，双向各重叠一句

    首段：向后取下一段的首句
    末段：向前取上一段的末句
    中间段：前后各取一句

    Returns:
        [(子切片文本, 子切片序号), ...]
    """
    paragraphs = [p.strip() for p in chunk_text.split("\n\n") if p.strip()]
    n = len(paragraphs)

    result = []
    for i, para in enumerate(paragraphs):
        parts = []

        if i > 0:
            parts.append(_get_last_sentence(paragraphs[i - 1]))

        parts.append(para)

        if i < n - 1:
            parts.append(_get_first_sentence(paragraphs[i + 1]))

        result.append(("".join(parts), i))

    return result


class DocIngestion:
    """文档入库 — embedding + pgvector 写入

    依赖 KGPipeline 提供的大切片和实体标注数据。
    """

    def __init__(
        self,
        embedder: EmbeddingClient | None = None,
        pg_dsn: str = "",
    ):
        self.embedder = embedder or EmbeddingClient()
        self.pg_dsn = pg_dsn or get_pgvector_dsn()

    async def ingest(
        self,
        chunks: list[Any],
        entities_per_chunk: dict[int, list[str]],
        kg_graph_id: int | None = None,
        course_id: int | None = None,
        source: str = "",
    ) -> int:
        """执行完整入库

        Args:
            chunks: KGPipeline 产出的 DocumentChunk 列表
            entities_per_chunk: {chunk_index: [entity_name, ...]}
            kg_graph_id: 关联的知识图谱 ID
            course_id: 所属课程 ID
            source: 来源文件名

        Returns:
            写入的子切片数量
        """
        # Step 1: 段落分割 — 大切片 → 子切片
        all_sub_chunks: list[dict] = []
        for chunk in chunks:
            sub_texts = split_sub_chunks(chunk.text)
            entities = entities_per_chunk.get(chunk.chunk_index, [])

            for sub_text, sub_idx in sub_texts:
                heading_path = getattr(chunk, "heading_path", [])
                all_sub_chunks.append({
                    "text": sub_text,
                    "parent_index": chunk.chunk_index,
                    "sub_index": sub_idx,
                    "entities": entities,
                    "heading_path": heading_path,
                })

        if not all_sub_chunks:
            return 0

        # Step 2: 批量产 embedding
        texts = [s["text"] for s in all_sub_chunks]
        embeddings = await self.embedder.batch_encode(texts)

        # Step 3: 批量写入 pgvector
        inserted = await self._batch_insert(
            all_sub_chunks, embeddings,
            kg_graph_id, course_id, source,
        )

        logger.info(
            "Ingested %d sub-chunks from %d parent chunks (source=%s)",
            inserted, len(chunks), source,
        )
        return inserted

    async def _batch_insert(
        self,
        sub_chunks: list[dict],
        embeddings: list[list[float]],
        kg_graph_id: int | None,
        course_id: int | None,
        source: str,
    ) -> int:
        """批量写入 document_chunks 表"""
        conn = await asyncpg.connect(self.pg_dsn)
        try:
            async with conn.transaction():
                records = []
                for i, sub in enumerate(sub_chunks):
                    metadata = {
                        "source": source,
                        "entities": sub["entities"],
                        "heading_path": sub["heading_path"],
                        "chapter_path": (
                            " > ".join(sub["heading_path"])
                            if sub["heading_path"] else ""
                        ),
                    }
                    records.append((
                        sub["text"],
                        str(embeddings[i]),  # list → "[0.0199, -0.0138, ...]"
                        json.dumps(metadata),
                        kg_graph_id,
                        course_id,
                        sub["sub_index"],
                        sub["parent_index"],
                    ))

                await conn.executemany(
                    """
                    INSERT INTO document_chunks
                        (chunk_text, embedding, metadata, kg_graph_id,
                         course_id, chunk_index, parent_chunk_index)
                    VALUES ($1, $2::vector, $3::jsonb, $4, $5, $6, $7)
                    """,
                    records,
                )
            return len(sub_chunks)
        finally:
            await conn.close()
