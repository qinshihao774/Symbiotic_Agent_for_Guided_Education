"""知识图谱后处理剪枝守卫

两层规则化过滤，作为 LLM 抽取的兜底保障：
1. filter_chunk_graph — 逐 chunk 过滤（类型白名单、名称质量、边校验、关系词表归一化）
2. prune_global_graph — 全局剪枝（孤立节点剔除、关系词表兜底、规模上限截断）

ID 规范化也在此完成（filter_chunk_graph 层），以便合并阶段跨 chunk 去重。
"""

import re

import networkx as nx

from app.kg_pipeline.models import EntityType, KGNode, KGEdge, KnowledgeGraph3D


# ---------------------------------------------------------------------------
# 常量（集中于此便于调参）
# ---------------------------------------------------------------------------

# LLM 可产出的 6 种核心类型（TERM/CHAPTER 不在其中）
CORE_TYPES: frozenset[EntityType] = frozenset({
    EntityType.CONCEPT,
    EntityType.ALGORITHM,
    EntityType.DATA_STRUCTURE,
    EntityType.PROTOCOL,
    EntityType.PRINCIPLE,
    EntityType.TECHNOLOGY,
})

# 受控关系词表（LLM 只能从中选取）
RELATION_VOCABULARY: frozenset[str] = frozenset({
    "包含", "属于", "使用", "依赖", "实现",
    "基于", "组成部分", "前提", "应用",
})

# 同义词归一化映射：同义 → 词表内标准名
RELATION_SYNONYMS: dict[str, str] = {
    "使用到": "使用",
    "应用了": "应用",
    "包括": "包含",
    "包含于": "属于",
    "前置于": "前提",
    "是前提": "前提",
}

# 通用非实体词（单独出现时几乎不可能是知识点）
GENERIC_NODE_NAMES: frozenset[str] = frozenset({
    "概念", "概述", "特点", "作用", "定义",
    "简介", "介绍", "说明", "总结", "结构",
})

# 知识点节点规模上限（目标：整本教材 200~500）。
# 章节节点不计入此上限，永远全保留。
MAX_GLOBAL_NODES: int = 500

_FULLWIDTH_TRANS = str.maketrans("（）：，。", "():,.")


def normalize_name(name: str) -> str:
    """名称/ID 规范化：去空白、全角→半角、折叠空格、去尾部编号"""
    name = name.strip()
    name = name.translate(_FULLWIDTH_TRANS)
    name = re.sub(r"\s+", " ", name)
    # 去尾部编号：仅剥离带括号的编号或带编号标点的编号，如 (1) / （1） / 1. / 1、
    # （要求括号成对或带编号标点，保留裸尾随数字如 "IPv6" / "HTTP/2"）
    name = re.sub(r"\s*(?:[（(]\d+[）)]|[（(]?\d+[）)]?[\.、．])\s*$", "", name)
    return name.strip()


def is_valid_node_name(name: str) -> bool:
    """节点名称质量检查：非空、非纯符号/数字、非通用词"""
    name = name.strip()
    if not name:
        return False
    if name in GENERIC_NODE_NAMES:
        return False
    if re.fullmatch(r"[\d\s\W_]+", name):
        return False
    return True


def normalize_relationship(rel: str | None) -> str | None:
    """关系名归一化：词表内原样返回；同义词映射；其余返回 None（丢弃）"""
    rel = (rel or "").strip()
    if rel in RELATION_VOCABULARY:
        return rel
    return RELATION_SYNONYMS.get(rel)


def filter_chunk_graph(kg: KnowledgeGraph3D) -> KnowledgeGraph3D:
    """逐 chunk 过滤：类型白名单 + 名称质量 + ID 规范化 + 边校验 + 关系词表

    Args:
        kg: 单个 chunk 抽取的图

    Returns:
        过滤后的图（节点 id/name 已规范化，边端点已重映射）
    """
    # 1. 节点：白名单 + 名称质量，构建 old_id → new_id 映射
    new_nodes: list[KGNode] = []
    id_map: dict[str, str] = {}
    for n in kg.nodes:
        if n.type not in CORE_TYPES:
            continue
        new_id = normalize_name(n.id)
        new_name = normalize_name(n.name) or new_id
        if not is_valid_node_name(new_name):
            continue
        id_map[n.id] = new_id
        new_nodes.append(KGNode(
            id=new_id,
            name=new_name,
            type=n.type,
            description=n.description.strip(),
            source_chunk_index=n.source_chunk_index,
        ))

    # 2. 边：端点重映射、去自环、关系词表归一化
    new_edges: list[KGEdge] = []
    for e in kg.edges:
        src = id_map.get(e.source_node_id)
        tgt = id_map.get(e.target_node_id)
        if src is None or tgt is None or src == tgt:
            continue
        rel = normalize_relationship(e.relationship_name)
        if rel is None:
            continue
        new_edges.append(KGEdge(
            source_node_id=src,
            target_node_id=tgt,
            relationship_name=rel,
            description=(e.description or "").strip() or None,
        ))

    return KnowledgeGraph3D(nodes=new_nodes, edges=new_edges)


def prune_global_graph(G: nx.DiGraph, max_nodes: int = MAX_GLOBAL_NODES) -> nx.DiGraph:
    """全局剪枝（原地修改）：孤立节点剔除、关系词表兜底、知识点规模上限截断

    Args:
        G: 合并后的 NetworkX DiGraph（含章节节点 + 知识点节点）
        max_nodes: 知识点节点规模上限（默认 500）。章节节点不计入此上限，永远全保留

    Returns:
        剪枝后的同一张图
    """
    # 1. 孤立节点剔除（仅当存在章节节点时——无章节说明无挂载预期，不做剔除）
    has_chapter = any(
        d.get("type") == EntityType.CHAPTER.value for _, d in G.nodes(data=True)
    )
    if has_chapter:
        isolated = [n for n, deg in dict(G.degree()).items() if deg == 0]
        if isolated:
            G.remove_nodes_from(isolated)

    # 2. 关系词表兜底（自动挂载的"包含"、跨章节的"依赖"均在词表内）
    for u, v, data in list(G.edges(data=True)):
        if normalize_relationship(data.get("relationship_name", "")) is None:
            G.remove_edge(u, v)

    # 3. 规模上限：章节节点不计入预算（永远全保留），按 (有描述, 度) 截断知识点
    if G.number_of_nodes() <= max_nodes:
        return G

    chapter_set = {
        n for n, d in G.nodes(data=True)
        if d.get("type") == EntityType.CHAPTER.value
    }
    non_chapters = [n for n in G.nodes if n not in chapter_set]
    scored = sorted(
        non_chapters,
        key=lambda n: (
            int(bool(G.nodes[n].get("description"))),
            int(G.degree(n)),
        ),
        reverse=True,
    )
    keep = chapter_set | set(scored[:max_nodes])
    for n in list(G.nodes):
        if n not in keep:
            G.remove_node(n)  # 同时删除关联边，无悬挂边
    return G
