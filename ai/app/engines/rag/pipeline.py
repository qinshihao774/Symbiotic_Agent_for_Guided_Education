"""RAG Pipeline — 三阶段排序（向量检索 → 图信号融合 → reranker 精排）"""

import logging
from dataclasses import dataclass, field
from enum import Enum

import asyncpg

from app.config import settings, get_pgvector_dsn
from app.engines.rag.embedding import EmbeddingClient
from app.engines.rag.reranker import RerankerClient

logger = logging.getLogger(__name__)


def _age_escape(value: str) -> str:
    """Safe escaping for Cypher string literals"""
    return value.replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n")


class DetailLevel(str, Enum):
    TEXT = "text"
    ENTITIES = "entities"
    SUBGRAPH = "subgraph"


@dataclass
class ChunkResult:
    """候选切片 — 三阶段逐步填充评分"""
    chunk_id: int
    text: str
    metadata: dict
    entities: list[str] = field(default_factory=list)
    chapter_path: str = ""

    # Stage 1 - 向量检索
    cosine_score: float = 0.0

    # Stage 2 - 图信号融合
    graph_distance: int = -1
    graph_degree: float = 0.0
    fused_score: float = 0.0

    # Stage 3 - Reranker
    rerank_score: float = 0.0


class RagPipeline:
    """RAG 查询管道 — 串联 embedding → pgvector → 图信号 → reranker

    用法:
        pipeline = RagPipeline()
        result = await pipeline.run("什么是共享栈", top_k=5)
    """

    def __init__(
        self,
        embedder: EmbeddingClient | None = None,
        pg_dsn: str = "",
        reranker: RerankerClient | None = None,
    ):
        self.embedder = embedder or EmbeddingClient(
            query_prefix="Represent this sentence for searching relevant passages: ",
        )
        self.pg_dsn = pg_dsn or get_pgvector_dsn()
        self.reranker = reranker or RerankerClient()

    async def run(
        self,
        query: str,
        top_k: int = 5,
        detail_level: DetailLevel = DetailLevel.TEXT,
        course_id: int | None = None,
        kg_graph_ids: list[int] | None = None,
    ) -> str:
        """执行完整 RAG 查询

        Args:
            query: 用户问题
            top_k: 最终返回片段数
            detail_level: 详细程度
            course_id: 按课程过滤（可选）
            kg_graph_ids: 按知识图谱 ID 过滤（可选，None 或空列表不过滤）
        """
        # Stage 1: 查询向量化 + pgvector 粗排
        query_vec = await self.embedder.encode(query)
        candidates = await self._vector_search(query_vec, course_id=course_id, kg_graph_ids=kg_graph_ids)

        if not candidates:
            return self._empty_result(query)

        # Stage 2: 图信号融合
        fused = await self._graph_fusion(candidates)

        # Stage 3: Reranker 精排
        ranked = await self._rerank_final(query, fused, top_k)

        # 格式化输出
        return self._format_output(query, ranked, detail_level)

    # ── 向量检索 ──────────────────────────────────────────────

    async def _vector_search(
        self,
        query_vec: list[float],
        course_id: int | None = None,
        kg_graph_ids: list[int] | None = None,
        limit: int | None = None,
    ) -> list[ChunkResult]:
        """pgvector ANN 搜索 — 余弦距离

        Args:
            kg_graph_ids: 按知识图谱 ID 过滤（可选，None 或空列表不过滤）
        """
        if limit is None:
            limit = settings.RAG_VECTOR_TOP_K
        try:
            conn = await asyncpg.connect(self.pg_dsn)
            try:
                query_vec_str = str(query_vec)
                rows = await conn.fetch(
                    """
                    SELECT id, chunk_text, metadata,
                           embedding <=> $1::vector AS distance
                    FROM document_chunks
                    WHERE embedding IS NOT NULL
                      AND ($2::bigint IS NULL OR course_id = $2)
                      AND ($4::bigint[] IS NULL OR kg_graph_id = ANY($4))
                    ORDER BY distance ASC
                    LIMIT $3
                    """,
                    query_vec_str,
                    course_id,
                    limit,
                    kg_graph_ids if kg_graph_ids else None,
                )
                # Fallback: if course_id filter yields nothing but kg_graph_ids
                # has data, retry without course_id (course_id may be NULL in DB)
                if not rows and course_id is not None and kg_graph_ids:
                    rows = await conn.fetch(
                        """
                        SELECT id, chunk_text, metadata,
                               embedding <=> $1::vector AS distance
                        FROM document_chunks
                        WHERE embedding IS NOT NULL
                          AND kg_graph_id = ANY($3)
                        ORDER BY distance ASC
                        LIMIT $2
                        """,
                        query_vec_str,
                        limit,
                        kg_graph_ids,
                    )
                results = []
                for row in rows:
                    meta = row["metadata"]
                    if isinstance(meta, str):
                        import json
                        meta = json.loads(meta) if meta else {}
                    elif meta is None:
                        meta = {}
                    entities = meta.get("entities", [])
                    chapter_path = meta.get("chapter_path", "")
                    results.append(ChunkResult(
                        chunk_id=row["id"],
                        text=row["chunk_text"],
                        metadata=meta,
                        entities=entities,
                        chapter_path=chapter_path,
                        cosine_score=1.0 - float(row["distance"]),
                    ))
                return results
            finally:
                await conn.close()
        except Exception as e:
            logger.error("Vector search failed: %s", e)
            return []

    # ── 图信号融合 ───────────────────────────────────────────

    async def _graph_fusion(
        self,
        candidates: list[ChunkResult],
    ) -> list[ChunkResult]:
        """乘法融合评分: score = cosine × dist_weight × degree_weight

        图信号从 AGE 获取（通过 psycopg2 + cypher 查询）。
        """
        if not candidates:
            return []

        # 收集所有实体名
        all_entities = set()
        for c in candidates:
            all_entities.update(c.entities)

        if not all_entities:
            # 无实体信息，降级为纯向量排序
            candidates.sort(key=lambda c: c.cosine_score, reverse=True)
            return candidates[:settings.RAG_FUSION_TOP_K]

        try:
            # 查 AGE 获取实体图距离和度
            # 使用与 kg_pipeline/storage.py 相同的 AGE 连接
            graph_info = await self._query_age_graph(list(all_entities))
        except Exception as e:
            logger.warning("AGE query failed, fallback to pure vector sort: %s", e)
            candidates.sort(key=lambda c: c.cosine_score, reverse=True)
            return candidates[:settings.RAG_FUSION_TOP_K]

        # 为每个候选计算融合分
        for c in candidates:
            degree_weight = self._graph_degree_factor(c.entities, graph_info)
            c.fused_score = c.cosine_score * degree_weight

        candidates.sort(key=lambda c: c.fused_score, reverse=True)
        return candidates[:settings.RAG_FUSION_TOP_K]

    def _graph_degree_factor(
        self, entities: list[str], graph_info: dict,
    ) -> float:
        """实体度权重 — 反映实体在网络中的重要性"""
        if not entities or not graph_info.get("max_degree", 0):
            return 1.0
        degrees = graph_info.get("entity_degrees", {})
        if not degrees:
            return 1.0
        avg_degree = sum(degrees.get(e, 0) for e in entities) / len(entities)
        max_deg = graph_info["max_degree"]
        from math import log
        return (log(avg_degree + 1) / log(max_deg + 1)) if max_deg > 0 else 1.0

    async def _query_age_graph(self, entities: list[str]) -> dict:
        """查 AGE 获取实体出度（通过 asyncio.to_thread 避免阻塞事件循环）"""
        import asyncio
        return await asyncio.to_thread(self._query_age_graph_sync, entities)

    def _query_age_graph_sync(self, entities: list[str]) -> dict:
        """同步查询 AGE 获取实体出度"""
        import psycopg2

        dsn = (
            f"host={settings.AGE_HOST} port={settings.AGE_PORT} "
            f"dbname={settings.AGE_DB} user={settings.AGE_USER} "
            f"password={settings.AGE_PASSWORD}"
        )
        conn = psycopg2.connect(dsn)
        conn.set_session(autocommit=True)
        try:
            with conn.cursor() as cur:
                cur.execute("LOAD 'age'")
                cur.execute("SET search_path TO ag_catalog, public")

                # 从数据库 kg_graphs 表解析真实存在的图谱，而非硬编码默认图
                from app.kg_pipeline.graph_registry import resolve_default_graph
                resolved = resolve_default_graph()
                if not resolved:
                    return {"entity_degrees": {}, "max_degree": 0}
                graph_name = _age_escape(resolved)

                # 查询实体出度
                entity_degrees = {}
                for ent in entities:
                    safe = _age_escape(ent)
                    cur.execute(
                        f"SELECT * FROM cypher('{graph_name}', $$ "
                        f"MATCH (n:Entity {{name: '{safe}'}})-[r]->() "
                        f"RETURN count(r) $$) AS (degree agtype)"
                    )
                    row = cur.fetchone()
                    degree = int(str(row[0])) if row and row[0] is not None else 0
                    entity_degrees[ent] = degree

                max_degree = max(entity_degrees.values()) if entity_degrees else 0

            return {
                "entity_degrees": entity_degrees,
                "max_degree": max_degree,
            }
        finally:
            conn.close()

    # ── Reranker 精排 ─────────────────────────────────────────

    async def _rerank_final(
        self,
        query: str,
        candidates: list[ChunkResult],
        top_k: int,
    ) -> list[ChunkResult]:
        """BGE-Reranker 重打分"""
        if not candidates:
            return []

        try:
            pairs = [(query, c.text) for c in candidates]
            scores = await self.reranker.rerank(pairs)
            for i, c in enumerate(candidates):
                if i < len(scores):
                    c.rerank_score = scores[i]
            candidates.sort(key=lambda c: c.rerank_score, reverse=True)
        except Exception as e:
            logger.warning("Reranker failed, fallback to fused score sort: %s", e)
            # 如果 reranker 不可用，按融合分排序
            candidates.sort(
                key=lambda c: c.fused_score if c.fused_score != 0.0 else c.cosine_score,
                reverse=True,
            )

        return candidates[:top_k]

    # ── 格式化输出 ─────────────────────────────────────────

    def _empty_result(self, query: str) -> str:
        return f"未在已上传文档中找到与 '{query}' 相关的内容。"

    def _format_output(
        self,
        query: str,
        results: list[ChunkResult],
        detail: DetailLevel,
    ) -> str:
        if not results:
            return self._empty_result(query)

        lines = [
            f"文档检索结果（关键词: {query}，共 {len(results)} 个片段）:\n"
        ]

        for i, r in enumerate(results):
            lines.append(f"--- 片段 {i + 1} ---")
            lines.append(r.text)
            lines.append("")

            if detail == DetailLevel.TEXT:
                continue

            if r.entities:
                lines.append(f"涉及知识点：{'、'.join(r.entities)}")

            if detail == DetailLevel.ENTITIES:
                lines.append("")
                continue

            if r.chapter_path:
                lines.append(f"章节路径：{r.chapter_path}")

            lines.append("")

        return "\n".join(lines)
