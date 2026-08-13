"""知识图谱查询工具"""
import logging

from app.agent.context import current_graph_names
from app.agent.node_semantic_search import semantic_search_nodes
from app.agent.tool_registry import ToolRegistry
from app.kg_pipeline.queries import search_nodes, GraphQueryError

logger = logging.getLogger(__name__)


@ToolRegistry.register(
    name="search_kg",
    description="查询知识图谱中的概念节点和关系。用于查找计算机学科相关的知识点、算法、数据结构等信息。query每次有且仅能输入一个知识点，如果需要搜索多个知识点，需要分别请求",
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "搜索关键词，如'红黑树'、'TCP三次握手'等",
            },
            "top_k": {
                "type": "integer",
                "description": "返回的最大节点数，默认10",
            },
        },
        "required": ["query"],
    },
)
async def search_kg(user_id: int, query: str, top_k: int = 10) -> str:
    """查询知识图谱中的概念节点和关系"""
    try:
        graph_names = current_graph_names.get()
        # 空列表或无图谱 → 从数据库解析真实存在的图谱
        if not graph_names:
            from app.kg_pipeline.graph_registry import list_graph_names
            graph_names = list_graph_names(status=None)
        if not graph_names:
            nodes = []
        else:
            all_nodes: list[dict] = []
            seen: set[str] = set()
            for gname in graph_names:
                try:
                    batch = search_nodes(query, graph_name=gname)
                    for node in batch:
                        nid = node.get("id", "")
                        if nid not in seen:
                            seen.add(nid)
                            all_nodes.append(node)
                except Exception as e:
                    logger.warning(f"search_kg: graph '{gname}' query failed: {e}")
                    continue
            nodes = all_nodes

        semantic_fallback = False
        if not nodes:
            try:
                # The exact/substring lookup missed. Compare the query embedding
                # with every node-name embedding and take the nearest node.
                nodes = await semantic_search_nodes(
                    query,
                    graph_names=graph_names or None,
                    top_k=1,
                )
                semantic_fallback = bool(nodes)
            except Exception as e:
                # Embedding is a fallback only. Keep the original not-found
                # response if the embedding service is temporarily unavailable.
                logger.warning("search_kg semantic fallback failed: %s", e)

        if not nodes:
            return f"未在知识图谱中找到与 '{query}' 相关的概念。建议尝试其他关键词。"

        limited = nodes[:top_k]
        fallback_note = "（节点名语义降级命中）" if semantic_fallback else ""
        output_lines = [
            f"知识图谱查询结果{fallback_note}（关键词: {query}，"
            f"共 {len(nodes)} 个结果，展示前 {len(limited)} 个）:\n"
        ]

        for node in limited:
            output_lines.append(
                # Preserve the source graph because the agent forwards this
                # result as the graph_name in the kg_hit event.
                f"- {node['name']} [{node.get('type', 'Concept')}] "
                f"(id:{node['id']}, graph:{node.get('graph_name', '')}): "
                f"{node.get('description', '无描述')}"
            )

        return "\n".join(output_lines)
    except GraphQueryError as e:
        logger.error(f"KG query failed: {e}")
        return f"知识图谱查询失败: {str(e)}"
