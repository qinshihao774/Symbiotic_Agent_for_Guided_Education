"""根据知识图谱邻居节点生成推荐问题"""

import asyncio
import json
import logging
from dataclasses import dataclass

from app.engines.llm.client import LLMClient
from app.engines.llm.profiles import deepseek_profile
from app.kg_pipeline.neighbors import NeighborInfo

logger = logging.getLogger(__name__)

SUGGESTIONS_PROMPT = """\
你是一个知识导航助手。用户刚刚了解了"{hit_node_name}"（{hit_node_type}）。

以下是该知识点的相关方向：
{neighbors_formatted}

请从中选择最值得深入了解的 {num_questions} 个方向，为每个方向生成一个自然、具体的问题。
问题应该引导用户进一步探索，而不是简单的"什么是X"。

只输出 JSON 数组，不要输出其他内容：
[{{"text": "问题文本", "node_id": "对应节点ID"}}]"""

SUGGESTIONS_TIMEOUT = 10.0


@dataclass
class SuggestedQuestion:
    """推荐问题"""
    text: str
    node_id: str
    node_name: str
    node_type: str
    relation: str


def _format_neighbors(neighbors: list[NeighborInfo]) -> str:
    """将邻居节点格式化为 LLM 可读的文本"""
    lines = []
    for i, n in enumerate(neighbors, 1):
        direction = {
            "upstream": "前置知识",
            "downstream": "后续知识",
            "both": "关联知识",
        }.get(n.relation, "关联知识")
        desc = f"：{n.description}" if n.description else ""
        lines.append(f"{i}. [{direction}] {n.node_name}（{n.node_type}，id:{n.node_id}）{desc}")
    return "\n".join(lines)


async def generate_suggested_questions(
    hit_node_name: str,
    hit_node_type: str,
    neighbors: list[NeighborInfo],
    conversation_context: str,
    llm_client: LLMClient,
    num_questions: int = 3,
) -> list[SuggestedQuestion]:
    """调用 LLM 将邻居节点润色为自然问题。

    Args:
        hit_node_name: 命中节点名称
        hit_node_type: 命中节点类型
        neighbors: 邻居节点列表
        conversation_context: 最近对话摘要（用于上下文感知）
        llm_client: LLM 客户端
        num_questions: 生成问题数量

    Returns:
        推荐问题列表。如果 LLM 调用失败或解析失败，返回空列表。
    """
    if not neighbors:
        return []

    neighbors_formatted = _format_neighbors(neighbors)
    prompt = SUGGESTIONS_PROMPT.format(
        hit_node_name=hit_node_name,
        hit_node_type=hit_node_type,
        neighbors_formatted=neighbors_formatted,
        num_questions=min(num_questions, len(neighbors)),
    )

    messages = [
        {"role": "system", "content": "你是一个知识导航助手，只输出 JSON 格式的推荐问题。"},
        {"role": "user", "content": prompt},
    ]

    # Add conversation context if available
    if conversation_context:
        messages.insert(1, {"role": "user", "content": f"对话背景：{conversation_context}"})

    try:
        response = await asyncio.wait_for(
            llm_client.chat(
                messages,
                temperature=0.5,
                profile=deepseek_profile(),
                response_format={"type": "json_object"},
            ),
            timeout=SUGGESTIONS_TIMEOUT,
        )

        if not response.content:
            logger.warning("LLM returned empty content for suggestions")
            return []

        # Parse JSON from response
        content = response.content.strip()
        # Handle case where LLM wraps JSON in markdown code block
        if content.startswith("```"):
            content = content.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

        parsed = json.loads(content)

        # Handle both array and object-with-array-key responses
        if isinstance(parsed, dict):
            # Try common keys
            for key in ("questions", "suggestions", "items", "data"):
                if key in parsed and isinstance(parsed[key], list):
                    parsed = parsed[key]
                    break
            else:
                # If still a dict, treat values as the list
                logger.warning(f"Unexpected dict format in suggestions response: {list(parsed.keys())}")
                return []

        if not isinstance(parsed, list):
            logger.warning(f"Expected list from suggestions LLM, got {type(parsed)}")
            return []

        # Build SuggestedQuestion list, matching node_id back to neighbor info
        neighbor_by_id = {n.node_id: n for n in neighbors}
        results: list[SuggestedQuestion] = []

        for item in parsed[:num_questions]:
            if not isinstance(item, dict):
                continue
            text = item.get("text", "").strip()
            node_id = item.get("node_id", "").strip()
            if not text or not node_id:
                continue

            neighbor = neighbor_by_id.get(node_id)
            if not neighbor:
                # LLM may have hallucinated a node_id; skip it
                logger.debug(f"Suggestion node_id '{node_id}' not found in neighbors, skipping")
                continue

            results.append(SuggestedQuestion(
                text=text,
                node_id=neighbor.node_id,
                node_name=neighbor.node_name,
                node_type=neighbor.node_type,
                relation=neighbor.relation,
            ))

        return results

    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse suggestions JSON: {e}")
        return []
    except asyncio.TimeoutError:
        logger.warning("Suggestions LLM call timed out")
        return []
    except Exception as e:
        logger.error(f"Failed to generate suggestions: {e}")
        return []
