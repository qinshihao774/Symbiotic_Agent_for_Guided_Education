"""Semantic vector lookup over embeddings stored in AGE properties."""

import logging
from typing import Sequence

import asyncpg

from app.config import get_pgvector_dsn, settings

logger = logging.getLogger(__name__)


def _quote_identifier(value: str) -> str:
    """Quote a PostgreSQL identifier such as an AGE graph schema name."""
    return '"' + value.replace('"', '""') + '"'


async def search_node_embeddings(
    query_vector: Sequence[float],
    graph_names: Sequence[str] | None = None,
    *,
    top_k: int = 1,
) -> list[dict]:
    """Return the nearest nodes using vectors inside AGE node properties."""
    if top_k <= 0:
        return []

    selected_graphs = list(graph_names or [])
    if not selected_graphs:
        # 从数据库 kg_graphs 表解析真实存在的图谱，而非硬编码默认图
        from app.kg_pipeline.graph_registry import list_graph_names
        selected_graphs = list_graph_names(status=None)
    if not selected_graphs:
        return []

    conn = None
    scored: list[tuple[float, dict]] = []
    try:
        conn = await asyncpg.connect(get_pgvector_dsn())
        for graph_name in selected_graphs:
            entity_table = (
                f"{_quote_identifier(graph_name)}.{_quote_identifier('Entity')}"
            )
            try:
                rows = await conn.fetch(
                    f"""
                    SELECT properties::text::jsonb ->> 'id' AS node_id,
                           properties::text::jsonb ->> 'name' AS node_name,
                           properties::text::jsonb ->> 'type' AS node_type,
                           properties::text::jsonb ->> 'description' AS description,
                           1 - (
                               (((properties::text::jsonb -> 'embedding')::text)
                                   ::vector({settings.BGE_M3_DIM}))
                               <=> $1::vector
                           ) AS semantic_score
                    FROM {entity_table}
                    WHERE properties::text::jsonb ? 'embedding'
                    ORDER BY
                        (((properties::text::jsonb -> 'embedding')::text)
                            ::vector({settings.BGE_M3_DIM}))
                        <=> $1::vector
                    LIMIT $2
                    """,
                    str(list(query_vector)),
                    top_k,
                )
            except (asyncpg.UndefinedTableError, asyncpg.UndefinedColumnError) as e:
                logger.warning(
                    "AGE semantic node lookup unavailable for graph '%s': %s",
                    graph_name,
                    e,
                )
                continue

            for row in rows:
                score = float(row["semantic_score"])
                scored.append((score, {
                    "id": row["node_id"],
                    "name": row["node_name"] or row["node_id"],
                    "type": row["node_type"] or "Concept",
                    "description": row["description"] or "",
                    "graph_name": graph_name,
                    "semantic_score": score,
                    "match_type": "age_property_semantic",
                }))
    except Exception as e:
        # Graphs may not have been backfilled yet. The caller retains its
        # runtime node-name embedding fallback.
        logger.warning("AGE property embedding lookup unavailable: %s", e)
        return []
    finally:
        if conn is not None:
            await conn.close()

    scored.sort(key=lambda item: item[0], reverse=True)
    return [node for _, node in scored[:top_k]]
