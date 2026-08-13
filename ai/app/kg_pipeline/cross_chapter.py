"""跨章节依赖抽取

按章节对，LLM 判断跨章节依赖关系。
"""

import logging
import os
from typing import Optional

import networkx as nx

from app.kg_pipeline.models import EntityType, KGEdge
from app.kg_pipeline.extraction import _parse_llm_json_response
from app.engines.llm.client import LLMClient
from app.engines.llm.profiles import ModelProfile
from app.config import settings


logger = logging.getLogger(__name__)

PROMPT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "prompts")

# 每个章节对最多输出的依赖边数
MAX_DEPS_PER_PAIR = 5


def _kg_extraction_profile() -> ModelProfile:
    """KG 抽取专用 profile"""
    return ModelProfile(
        base_url=settings.KG_MODEL_BASE_URL,
        model_name=settings.KG_MODEL_NAME,
        api_key=settings.KG_MODEL_API_KEY,
        timeout=120.0,
    )


def _load_cross_chapter_prompt() -> str:
    """加载跨章节依赖抽取 prompt"""
    path = os.path.join(PROMPT_DIR, "kg_cross_chapter.txt")
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _build_chapter_pairs(
    chapters: list[str],
    max_distance: Optional[int] = None,
) -> list[tuple[str, str]]:
    """生成去重的章节对

    Args:
        chapters: 章节名称列表（按文档顺序）
        max_distance: 最大章节索引距离，超过此距离的跳过（None 表示不限制）

    Returns:
        章节对列表，每对 (A, B) 中 A 的索引小于 B
    """
    pairs = []
    for i in range(len(chapters)):
        for j in range(i + 1, len(chapters)):
            if max_distance is not None and (j - i) > max_distance:
                continue
            pairs.append((chapters[i], chapters[j]))
    return pairs


def _build_cross_chapter_user_message(
    chapter_a: str,
    points_a: list[str],
    chapter_b: str,
    points_b: list[str],
) -> str:
    """构建跨章节依赖抽取的 user message

    Args:
        chapter_a: 章节 A 名称
        points_a: 章节 A 下所有知识点名称
        chapter_b: 章节 B 名称
        points_b: 章节 B 下所有知识点名称

    Returns:
        user message（不含系统提示）
    """
    points_a_str = "、".join(points_a) if points_a else "（无知识点）"
    points_b_str = "、".join(points_b) if points_b else "（无知识点）"

    return (
        f"章节A: {chapter_a}\n"
        f"知识点: {points_a_str}\n\n"
        f"章节B: {chapter_b}\n"
        f"知识点: {points_b_str}\n"
    )


class CrossChapterExtractor:
    """跨章节依赖抽取器"""

    def __init__(
        self,
        enable: bool = True,
        llm_client: Optional[LLMClient] = None,
        profile: Optional[ModelProfile] = None,
        max_distance: Optional[int] = 3,
    ):
        self.enable = enable
        self.llm = llm_client or LLMClient()
        self.profile = profile or _kg_extraction_profile()
        self.max_distance = max_distance

    async def extract(self, graph: nx.DiGraph) -> list[KGEdge]:
        """从图中抽取跨章节依赖

        Args:
            graph: 合并后的 NetworkX DiGraph（包含章节节点和知识点节点）

        Returns:
            跨章节依赖边列表
        """
        if not self.enable:
            return []

        # 1. 收集所有章节节点
        chapters = []
        for node_id, attrs in graph.nodes(data=True):
            if attrs.get("type") == EntityType.CHAPTER.value:
                chapters.append(node_id)

        if len(chapters) < 2:
            logger.info("[CrossChapter] Less than 2 chapters, skipping")
            return []

        # 2. 收集每个章节下的知识点
        chapter_points: dict[str, list[str]] = {ch: [] for ch in chapters}
        for ch in chapters:
            for _, target, attrs in graph.out_edges(ch, data=True):
                if attrs.get("relationship_name") == "包含":
                    target_type = graph.nodes[target].get("type", "")
                    if target_type != EntityType.CHAPTER.value:
                        chapter_points[ch].append(target)

        # 3. 生成章节对
        pairs = _build_chapter_pairs(chapters, max_distance=self.max_distance)
        logger.info(f"[CrossChapter] Checking {len(pairs)} chapter pairs")

        # 4. 逐对调用 LLM
        system_prompt = _load_cross_chapter_prompt()
        all_edges: list[KGEdge] = []
        for chapter_a, chapter_b in pairs:
            points_a = chapter_points.get(chapter_a, [])
            points_b = chapter_points.get(chapter_b, [])

            # 如果某个章节没有知识点，跳过
            if not points_a or not points_b:
                continue

            user_message = _build_cross_chapter_user_message(chapter_a, points_a, chapter_b, points_b)

            try:
                resp = await self.llm.chat(
                    [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message},
                    ],
                    temperature=0.1,
                    profile=self.profile,
                )
                raw = resp.content or ""
                data = _parse_llm_json_response(raw)
            except Exception as e:
                logger.warning(f"[CrossChapter] Failed for ({chapter_a}, {chapter_b}): {e}")
                continue

            # 5. 解析依赖关系（dependencies 非 list 时容错，避免单个章节对使整个构建中止）
            deps = data.get("dependencies", []) if isinstance(data, dict) else []
            if not isinstance(deps, list):
                deps = []
            for dep in deps[:MAX_DEPS_PER_PAIR]:
                source = dep.get("source", "")
                target = dep.get("target", "")
                relationship = dep.get("relationship", "依赖")
                description = dep.get("description", "")

                if not source or not target:
                    continue

                # 验证端点在图中
                if source not in graph or target not in graph:
                    logger.warning(f"[CrossChapter] Endpoint not in graph: {source} or {target}")
                    continue

                all_edges.append(KGEdge(
                    source_node_id=source,
                    target_node_id=target,
                    relationship_name=relationship,
                    description=description,
                ))

        logger.info(f"[CrossChapter] Found {len(all_edges)} cross-chapter dependencies")
        return all_edges
