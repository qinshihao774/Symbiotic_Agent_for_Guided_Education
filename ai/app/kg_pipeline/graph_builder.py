"""NetworkX 内存图构建与去重

合并章节节点 + 知识点节点，自动为知识点添加"所属章节 → 知识点"的包含边。
"""

import logging
from typing import Optional

import networkx as nx

from app.config import settings
from app.kg_pipeline.models import (
    DocumentChunk,
    EntityType,
    KGEdge,
    KGNode,
    KnowledgeGraph3D,
)
from app.kg_pipeline.pruning import prune_global_graph


logger = logging.getLogger(__name__)


class GraphBuilder:
    """合并多个切片的知识图谱为一张统一的内存图

    使用 NetworkX DiGraph 作为中间表示，
    在写入 AGE 前完成实体去重和边验证。
    """

    def build(
        self,
        chunk_graphs: list[KnowledgeGraph3D],
        chapter_graph: Optional[KnowledgeGraph3D] = None,
        chunks: Optional[list[DocumentChunk]] = None,
    ) -> nx.DiGraph:
        """合并多个 KnowledgeGraph3D 片段为统一图

        Args:
            chunk_graphs: 每个切片抽取的图片段（知识点）
            chapter_graph: 章节节点和 contains 边（来自 ChapterBuilder）
            chunks: 文档切片列表（用于知识点自动挂载章节）

        Returns:
            NetworkX DiGraph，节点属性含 name/type/description，
            边属性含 relationship_name/description
        """
        G = nx.DiGraph()

        # 1. 先添加章节节点和边
        if chapter_graph:
            self._add_knowledge_graph(G, chapter_graph)

        # 2. 再添加知识点节点和边
        for kg in chunk_graphs:
            self._add_knowledge_graph(G, kg)

        # 3. 自动挂载：为每个知识点添加"所属章节叶节点 → 知识点"的包含边
        if chunks:
            self._auto_mount_chapters(G, chunk_graphs, chunks)

        # 4. 全局剪枝：孤立节点剔除、关系词表兜底、规模上限
        if settings.KG_PRUNING_ENABLED:
            G = prune_global_graph(G)

        return G

    def _add_knowledge_graph(self, G: nx.DiGraph, kg: KnowledgeGraph3D) -> None:
        """将一个 KnowledgeGraph3D 的节点和边添加到图中"""
        for node in kg.nodes:
            if node.id in G:
                existing = G.nodes[node.id]
                if len(node.name) > len(existing.get("name", "")):
                    G.nodes[node.id]["name"] = node.name
                if len(node.description) > len(existing.get("description", "")):
                    G.nodes[node.id]["description"] = node.description
            else:
                G.add_node(
                    node.id,
                    name=node.name,
                    type=node.type.value if hasattr(node.type, 'value') else node.type,
                    description=node.description,
                    source_chunk_index=node.source_chunk_index,
                )

        for edge in kg.edges:
            if edge.source_node_id not in G:
                logger.warning(f"Edge source {edge.source_node_id} not in graph, skipping")
                continue
            if edge.target_node_id not in G:
                logger.warning(f"Edge target {edge.target_node_id} not in graph, skipping")
                continue

            key = (edge.source_node_id, edge.target_node_id)
            if G.has_edge(*key):
                existing_edge = G.edges[key]
                if existing_edge.get("relationship_name") == edge.relationship_name:
                    continue

            G.add_edge(
                edge.source_node_id,
                edge.target_node_id,
                relationship_name=edge.relationship_name,
                description=edge.description,
            )

    def _auto_mount_chapters(
        self,
        G: nx.DiGraph,
        chunk_graphs: list[KnowledgeGraph3D],
        chunks: list[DocumentChunk],
    ) -> None:
        """为知识点自动添加"所属章节叶节点 → 知识点"的包含边

        规则：
        - 源节点：chunk 的 heading_path 中最深层章节（叶节点）
        - 目标节点：该 chunk 抽取出的知识点
        - 关系名：包含
        """
        # 构建 chunk_index → heading_path 的映射
        chunk_heading_map: dict[int, list[str]] = {}
        for chunk in chunks:
            if chunk.heading_path:
                chunk_heading_map[chunk.chunk_index] = chunk.heading_path

        # 遍历每个 chunk_graph，为其中的知识点挂载章节
        for kg in chunk_graphs:
            for node in kg.nodes:
                # 跳过章节节点（它们已经在 chapter_graph 中了）
                node_type = node.type.value if hasattr(node.type, 'value') else node.type
                if node_type == EntityType.CHAPTER.value:
                    continue

                # 查找该知识点所属 chunk 的叶章节
                source_index = node.source_chunk_index
                if source_index is None or source_index not in chunk_heading_map:
                    continue

                heading_path = chunk_heading_map[source_index]
                if not heading_path:
                    continue

                # 叶章节 = heading_path 的最后一个元素
                leaf_chapter = heading_path[-1]

                # 检查叶章节节点是否在图中
                if leaf_chapter not in G:
                    logger.warning(f"Leaf chapter '{leaf_chapter}' not in graph, cannot mount '{node.id}'")
                    continue

                # 检查知识点节点是否在图中
                if node.id not in G:
                    continue

                # 检查边是否已存在
                if G.has_edge(leaf_chapter, node.id):
                    existing_edge = G.edges[leaf_chapter, node.id]
                    if existing_edge.get("relationship_name") == "包含":
                        continue

                # 添加包含边
                G.add_edge(
                    leaf_chapter,
                    node.id,
                    relationship_name="包含",
                    description=f"{leaf_chapter}包含{node.name or node.id}",
                )
