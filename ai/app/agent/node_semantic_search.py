"""Semantic fallback for knowledge-graph node-name lookup."""

import asyncio
from array import array
from dataclasses import dataclass
import logging
import math
from typing import Sequence

from app.engines.rag.embedding import EmbeddingClient
from app.kg_pipeline.age_semantic_store import search_node_embeddings
from app.kg_pipeline.graph_registry import list_graph_names
from app.kg_pipeline.queries import GraphQueryError, list_nodes

logger = logging.getLogger(__name__)

_EMBEDDING_BATCH_SIZE = 256


@dataclass(frozen=True)
class _CachedNodeEmbeddings:
    signature: tuple[tuple[str, str], ...]
    vectors: tuple[array, ...]


_index_cache: dict[str, _CachedNodeEmbeddings] = {}
_index_locks: dict[str, asyncio.Lock] = {}


def _node_signature(nodes: Sequence[dict]) -> tuple[tuple[str, str], ...]:
    return tuple((str(node.get("id", "")), str(node.get("name", ""))) for node in nodes)


async def _encode_node_names(
    cache_key: str,
    nodes: Sequence[dict],
    embedder: EmbeddingClient,
) -> tuple[array, ...]:
    """Build or reuse a graph's node-name embedding index."""
    signature = _node_signature(nodes)
    cached = _index_cache.get(cache_key)
    if cached is not None and cached.signature == signature:
        return cached.vectors

    lock = _index_locks.setdefault(cache_key, asyncio.Lock())
    async with lock:
        cached = _index_cache.get(cache_key)
        if cached is not None and cached.signature == signature:
            return cached.vectors

        names = [str(node.get("name", "")) for node in nodes]
        vectors: list[array] = []
        for start in range(0, len(names), _EMBEDDING_BATCH_SIZE):
            batch = names[start:start + _EMBEDDING_BATCH_SIZE]
            encoded = await embedder.batch_encode(batch)
            vectors.extend(array("f", vector) for vector in encoded)

        result = tuple(vectors)
        _index_cache[cache_key] = _CachedNodeEmbeddings(signature, result)
        logger.info("Built KG node-name embedding index: graph=%s, nodes=%d", cache_key, len(nodes))
        return result


def _cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right) or not left:
        return float("-inf")
    dot = math.fsum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(math.fsum(value * value for value in left))
    right_norm = math.sqrt(math.fsum(value * value for value in right))
    if left_norm == 0.0 or right_norm == 0.0:
        return float("-inf")
    return dot / (left_norm * right_norm)


async def semantic_search_nodes(
    query: str,
    graph_names: Sequence[str] | None = None,
    *,
    top_k: int = 1,
    embedder: EmbeddingClient | None = None,
) -> list[dict]:
    """Match a query against all node names and return the closest nodes."""
    if top_k <= 0:
        return []

    client = embedder or EmbeddingClient()
    requested_graphs: list[str | None] = list(graph_names) if graph_names else [None]
    persisted_graph_names = (
        list(graph_names)
        if graph_names
        else list_graph_names(status=None)
    )

    query_vector = await client.encode(query)
    persisted = await search_node_embeddings(
        query_vector,
        graph_names=persisted_graph_names,
        top_k=top_k,
    )
    if persisted:
        best = persisted[0]
        logger.info(
            "KG AGE-property semantic hit: query=%r, node=%r, graph=%s, score=%.4f",
            query,
            best.get("name"),
            best.get("graph_name", ""),
            best["semantic_score"],
        )
        return persisted

    async def load_graph_nodes(requested_graph: str | None) -> tuple[str | None, list[dict]]:
        try:
            nodes = await asyncio.to_thread(list_nodes, requested_graph)
        except GraphQueryError as e:
            logger.warning(
                "KG semantic fallback could not list graph '%s': %s",
                requested_graph or "<default>",
                e,
            )
            nodes = []
        return requested_graph, nodes

    loaded_graphs = await asyncio.gather(
        *(load_graph_nodes(graph_name) for graph_name in requested_graphs)
    )

    async def score_graph(
        requested_graph: str | None,
        nodes: list[dict],
    ) -> list[tuple[float, dict]]:
        if not nodes:
            return []
        cache_key = str(nodes[0].get("graph_name") or requested_graph or "<default>")
        try:
            vectors = await _encode_node_names(cache_key, nodes, client)
        except Exception as e:
            logger.warning(
                "KG semantic fallback could not build index for graph '%s': %s",
                cache_key,
                e,
            )
            return []
        if len(vectors) != len(nodes):
            logger.warning(
                "KG node embedding count mismatch: graph=%s, nodes=%d, vectors=%d",
                cache_key,
                len(nodes),
                len(vectors),
            )
            return []

        graph_scores = []
        for node, vector in zip(nodes, vectors):
            score = _cosine_similarity(query_vector, vector)
            if math.isfinite(score):
                graph_scores.append((score, node))
        return graph_scores

    # A cold cache can contain thousands of names across several selected
    # textbooks. Build each graph index concurrently so the agent's tool call
    # does not wait for every graph serially.
    scores_by_graph = await asyncio.gather(
        *(score_graph(requested_graph, nodes) for requested_graph, nodes in loaded_graphs)
    )
    scored = [item for graph_scores in scores_by_graph for item in graph_scores]

    scored.sort(key=lambda item: item[0], reverse=True)
    results = []
    seen: set[tuple[str, str]] = set()
    for score, node in scored:
        key = (str(node.get("graph_name", "")), str(node.get("id", "")))
        if key in seen:
            continue
        seen.add(key)
        result = dict(node)
        result["semantic_score"] = score
        result["match_type"] = "semantic_fallback"
        results.append(result)
        if len(results) >= top_k:
            break

    if results:
        best = results[0]
        logger.info(
            "KG semantic fallback hit: query=%r, node=%r, graph=%s, score=%.4f",
            query,
            best.get("name"),
            best.get("graph_name", ""),
            best["semantic_score"],
        )
    return results


def clear_node_embedding_cache() -> None:
    """Clear the process-local index (primarily useful for tests)."""
    _index_cache.clear()
    _index_locks.clear()
