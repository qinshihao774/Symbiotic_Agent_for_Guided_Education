"""LLM 实体与关系抽取器"""

import json
import logging
import os
import re
from typing import Optional

from app.kg_pipeline.models import DocumentChunk, KnowledgeGraph3D, KGNode, KGEdge
from app.kg_pipeline.pruning import filter_chunk_graph
from app.engines.llm.client import LLMClient
from app.engines.llm.profiles import ModelProfile, remote_profile
from app.config import settings


def _kg_extraction_profile() -> ModelProfile:
    """KG 抽取专用 profile：使用 deepseek-v4-flash"""
    return ModelProfile(
        base_url=settings.KG_MODEL_BASE_URL,
        model_name=settings.KG_MODEL_NAME,
        api_key=settings.KG_MODEL_API_KEY,
        timeout=120.0,
    )


logger = logging.getLogger(__name__)

PROMPT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "prompts")


def _load_prompt(filename: str = "kg_extraction.txt") -> str:
    """从 prompts 目录加载提示词文件"""
    path = os.path.join(PROMPT_DIR, filename)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _build_chapter_context(chunk: DocumentChunk) -> str:
    """构建章节上下文注入文本

    当 chunk 携带 heading_path 时，在 user message 开头注入章节上下文，
    提醒 LLM 不要提取章节标题，只提取具体知识点。

    Args:
        chunk: 文档切片

    Returns:
        章节上下文字符串，无 heading_path 时返回空字符串
    """
    if not chunk.heading_path:
        return ""

    path_str = " > ".join(chunk.heading_path)
    return (
        f"## 章节上下文\n\n"
        f"你正在处理教材的以下章节：\n"
        f"{path_str}\n\n"
        f"规则：\n"
        f"- 不要提取章节标题作为实体（章节节点已自动生成）\n"
        f"- 只提取章节内的具体知识点（算法、数据结构、概念等）\n"
        f"- 提取的知识点将自动归属于上述章节\n\n"
    )


def _repair_json(raw: str) -> Optional[str]:
    """尝试修复 LLM 常见的 JSON 格式错误

    支持：
    - 对象/数组末尾的尾随逗号
    - 单引号 JSON（仅在全文无双引号时转换，避免破坏字符串内的单引号）

    Args:
        raw: 原始 JSON 字符串

    Returns:
        修复后的 JSON 字符串；无需修复时返回 None
    """
    repaired = raw
    # 修复尾随逗号（逗号后紧跟 } 或 ]）
    repaired = re.sub(r",\s*}", "}", repaired)
    repaired = re.sub(r",\s*\]", "]", repaired)
    # 单引号转换：仅在完全没有双引号时进行
    if '"' not in repaired:
        repaired = repaired.replace("'", '"')
    if repaired != raw:
        return repaired
    return None


def _extract_partial_json(raw: str) -> Optional[dict]:
    """从损坏/截断的 JSON 中尽力提取 nodes/edges 数组

    单个数组无法解析时跳过，能提取到任意非空数组即返回，
    避免单个 chunk 的 LLM 输出瑕疵导致整本书构建失败。

    Args:
        raw: 无法整体解析的 LLM 响应文本

    Returns:
        含 nodes/edges 的 dict；未提取到任何非空数据时返回 None
    """
    result: dict = {"nodes": [], "edges": []}
    found = False
    for key in ("nodes", "edges"):
        m = re.search(rf'"{key}"\s*:\s*\[(.*?)\]', raw, re.DOTALL)
        if not m:
            continue
        inner = m.group(1)
        candidate = _repair_json(f"[{inner}]") or f"[{inner}]"
        try:
            arr = json.loads(candidate)
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(arr, list) and arr:
            result[key] = arr
            found = True
    return result if found else None


def _parse_llm_json_response(raw: str) -> dict:
    """从 LLM 响应中提取 JSON

    处理 LLM 返回 markdown 包裹的 JSON 代码块：
    ```json\n{"nodes": ...}\n```
    或裸 JSON。

    Raises:
        ValueError: 响应为空 / 不含 JSON 对象 / 所有修复手段均失败
    """
    if not isinstance(raw, str):
        raw = str(raw)

    code_block = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', raw, re.DOTALL)
    if code_block:
        raw = code_block.group(1).strip()

    # 截取首个 { 之后的内容，去掉 JSON 前的解释文字
    brace_start = raw.find('{')
    if brace_start >= 0:
        raw = raw[brace_start:]
    # 截取到最后一个 }，去掉 JSON 对象后的解释文字
    brace_end = raw.rfind('}')
    if brace_end >= 0:
        raw = raw[:brace_end + 1]

    if not raw.strip():
        raise ValueError("Empty LLM response")

    if '{' not in raw:
        raise ValueError("No JSON object found in LLM response")

    # 直接解析
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        pass

    # 修复常见错误后重试
    repaired = _repair_json(raw)
    if repaired is not None:
        try:
            return json.loads(repaired)
        except (json.JSONDecodeError, ValueError):
            pass

    # 部分提取（截断/严重损坏时抢救 nodes/edges）
    partial = _extract_partial_json(raw)
    if partial is not None:
        return partial

    raise ValueError("JSON parse failed after all recovery attempts")


class LlmExtractionError(Exception):
    """LLM 解析格式错误"""
    pass


class KGExtractor:
    """从文档切片中提取知识图谱"""

    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        profile: Optional[ModelProfile] = None,
        custom_prompt: Optional[str] = None,
    ):
        self.llm = llm_client or LLMClient()
        self.profile = profile or _kg_extraction_profile()
        self.system_prompt = custom_prompt or _load_prompt()

    async def extract_from_chunk(self, chunk: DocumentChunk) -> KnowledgeGraph3D:
        """从单个文本切片中抽取知识图谱
        
        Args:
            chunk: 文档切片
            
        Returns:
            KnowledgeGraph3D 包含抽取的节点和边

        Raises:
            LlmExtractionError: LLM 返回格式无法解析
        """
        # 构建章节上下文 + 原始文本
        chapter_context = _build_chapter_context(chunk)
        user_content = chapter_context + chunk.text

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_content},
        ]

        try:
            resp = await self.llm.chat(
                messages,
                temperature=0.1,
                profile=self.profile,
            )
        except Exception as e:
            raise LlmExtractionError(f"LLM call failed: {e}") from e

        raw = resp.content or ""

        try:
            data = _parse_llm_json_response(raw)
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Failed to parse LLM response: {raw[:200]}")
            raise LlmExtractionError(f"JSON parse failed: {e}") from e

        try:
            nodes = [
                KGNode(
                    id=n.get("id", n.get("name", "")),
                    name=n.get("name", n.get("id", "")),
                    type=n["type"],
                    description=n.get("description", ""),
                    source_chunk_index=chunk.chunk_index,
                )
                for n in data.get("nodes", [])
                if n.get("id") or n.get("name")
            ]
            edges = [
                KGEdge(
                    source_node_id=e["source_node_id"],
                    target_node_id=e["target_node_id"],
                    relationship_name=e["relationship_name"],
                    description=e.get("description"),
                )
                for e in data.get("edges", [])
                if e.get("source_node_id") and e.get("target_node_id")
            ]
        except (KeyError, TypeError) as e:
            raise LlmExtractionError(f"Field validation failed: {e}") from e

        kg = KnowledgeGraph3D(nodes=nodes, edges=edges)
        if settings.KG_PRUNING_ENABLED:
            kg = filter_chunk_graph(kg)
        return kg
