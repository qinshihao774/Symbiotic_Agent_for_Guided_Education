"""章节节点生成器

从所有 chunk 的 heading_path 去重，生成章节 KGNode + contains 边。
不用 LLM，100% 准确，零幻觉。
"""

import logging

from app.kg_pipeline.models import DocumentChunk, EntityType, KGNode, KGEdge, KnowledgeGraph3D


logger = logging.getLogger(__name__)


class ChapterBuilder:
    """从 chunk 的 heading_path 生成章节节点和层级边"""

    def build(self, chunks: list[DocumentChunk]) -> KnowledgeGraph3D:
        """从所有 chunk 的 heading_path 生成章节节点和 contains 边

        生成规则：
        1. 遍历所有 chunk 的 heading_path，收集所有唯一标题
        2. 每个唯一标题生成一个 type=Chapter 的 KGNode
        3. heading_path 中相邻元素之间生成 contains 边

        Args:
            chunks: 文档切片列表（需携带 heading_path 和 heading_levels）

        Returns:
            KnowledgeGraph3D 包含章节节点和 contains 边
        """
        nodes: dict[str, KGNode] = {}  # id -> KGNode, 去重
        edges: list[KGEdge] = []
        seen_edges: set[tuple[str, str]] = set()  # (source, target) 去重

        for chunk in chunks:
            path = chunk.heading_path
            if not path:
                continue

            # 为路径中每个标题生成 Chapter 节点
            for title in path:
                if title not in nodes:
                    nodes[title] = KGNode(
                        id=title,
                        name=title,
                        type=EntityType.CHAPTER,
                        description=f"教材章节：{title}",
                    )

            # 相邻元素之间生成 contains 边
            for i in range(len(path) - 1):
                source = path[i]
                target = path[i + 1]
                edge_key = (source, target)
                if edge_key not in seen_edges:
                    seen_edges.add(edge_key)
                    edges.append(KGEdge(
                        source_node_id=source,
                        target_node_id=target,
                        relationship_name="包含",
                        description=f"{source}包含{target}",
                    ))

        return KnowledgeGraph3D(
            nodes=list(nodes.values()),
            edges=edges,
        )
