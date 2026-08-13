"""查询知识图谱节点的 1-hop 邻居"""

import logging
from dataclasses import dataclass

from app.kg_pipeline.queries import GraphQueryError, _escape, _strip_agtype
from app.kg_pipeline.storage import AgeStorage, AgeConnectionError

logger = logging.getLogger(__name__)


@dataclass
class NeighborInfo:
    """邻居节点信息"""
    node_id: str
    node_name: str
    node_type: str
    relation: str  # "upstream" | "downstream" | "both"
    description: str


def get_node_neighbors(
    node_id: str,
    graph_name: str,
    max_neighbors: int = 6,
) -> list[NeighborInfo]:
    """查询指定节点的 1-hop 邻居，按信息丰富度排序取 top-N。

    Args:
        node_id: 中心节点的 ID
        graph_name: 图谱名称
        max_neighbors: 最多返回多少个邻居

    Returns:
        邻居节点列表，每个包含 node_id, node_name, node_type, relation, description。
        relation 为 "upstream"（边指向中心节点）、"downstream"（边从中心节点出发）、
        或 "both"（双向）。
    """
    storage = AgeStorage(graph_name=graph_name)
    try:
        conn = storage._get_conn()
    except AgeConnectionError as e:
        raise GraphQueryError(f"Cannot connect to AGE: {e}") from e

    try:
        with conn.cursor() as cur:
            cur.execute("LOAD 'age';")
            cur.execute("SET search_path TO ag_catalog, public;")

            # Query outgoing edges: center -> neighbor (downstream)
            cur.execute(
                f"SELECT * FROM cypher('{storage._graph_name}', $$ "
                f"MATCH (a:Entity)-[r:RELATION]->(b:Entity) "
                f"WHERE a.id = '{_escape(node_id)}' "
                f"RETURN b.id, b.name, b.type, b.description "
                f"$$) AS (id agtype, name agtype, type agtype, description agtype)"
            )
            downstream_rows = cur.fetchall()

            # Query incoming edges: neighbor -> center (upstream)
            cur.execute(
                f"SELECT * FROM cypher('{storage._graph_name}', $$ "
                f"MATCH (a:Entity)-[r:RELATION]->(b:Entity) "
                f"WHERE b.id = '{_escape(node_id)}' "
                f"RETURN a.id, a.name, a.type, a.description "
                f"$$) AS (id agtype, name agtype, type agtype, description agtype)"
            )
            upstream_rows = cur.fetchall()

    except Exception as e:
        logger.error(f"Neighbor query failed: {e}")
        raise GraphQueryError(str(e)) from e
    finally:
        conn.close()

    # Build neighbor map: node_id -> {name, type, description, relations: set}
    neighbor_map: dict[str, dict] = {}

    for row in downstream_rows:
        nid = _strip_agtype(row[0])
        if nid == node_id:
            continue
        if nid not in neighbor_map:
            neighbor_map[nid] = {
                "name": _strip_agtype(row[1]),
                "type": _strip_agtype(row[2]),
                "description": _strip_agtype(row[3]),
                "relations": set(),
            }
        neighbor_map[nid]["relations"].add("downstream")

    for row in upstream_rows:
        nid = _strip_agtype(row[0])
        if nid == node_id:
            continue
        if nid not in neighbor_map:
            neighbor_map[nid] = {
                "name": _strip_agtype(row[1]),
                "type": _strip_agtype(row[2]),
                "description": _strip_agtype(row[3]),
                "relations": set(),
            }
        neighbor_map[nid]["relations"].add("upstream")

    # Determine final relation and build result list
    results: list[NeighborInfo] = []
    for nid, info in neighbor_map.items():
        rels = info["relations"]
        if "upstream" in rels and "downstream" in rels:
            relation = "both"
        elif "upstream" in rels:
            relation = "upstream"
        else:
            relation = "downstream"

        results.append(NeighborInfo(
            node_id=nid,
            node_name=info["name"] or nid,
            node_type=info["type"] or "Concept",
            relation=relation,
            description=info["description"] or "",
        ))

    # Sort by description length as a proxy for information richness
    # (degree is not available from this query without extra work)
    results.sort(key=lambda n: len(n.description), reverse=True)

    return results[:max_neighbors]
