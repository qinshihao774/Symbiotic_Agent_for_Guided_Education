"""学生 AI 学习分析 Agent — 基于 ReAct + Observation 循环的真正 AI Agent

===== ReAct Agent 循环 =====

  ┌──────────┐    工具调用     ┌──────────┐
  │   LLM    │ ──────────────→ │  工具执行  │
  │ 推理+决策 │ ←────────────── │ (DB查询)  │
  └──────────┘    Observation  └──────────┘
       │
       │ 最终答案
       ▼
  结构化分析 JSON

===== 输出格式（与前端兼容） =====

返回的 dict 结构如下：
{
    "stu_id": int,
    "dimensions_available": int (0-3),
    "weights": {"level": float, "mastery": float, "wrong_exercises": float},
    "dimensions_detail": {
        "level": {"available": bool, "value": str|None},
        "mastery": {"available": bool, "node_count": int, "weakest_nodes": [...]},
        "wrong_exercises": {"available": bool, "total_count": int, "knowledge_summary": [...]}
    },
    "analysis": {summary, weakness_analysis, improvement_suggestions, comprehensive_rating, priority_focus} | None,
    "error": str | None
}
"""
import json
import logging
from typing import Any

from app.agent.tools.stu_analysis_db import (
    execute_analysis_tool,
    get_stu_analysis_tool_definitions,
)
from app.engines.llm.client import LLMClient
from app.engines.llm.profiles import deepseek_profile

logger = logging.getLogger(__name__)

# ── Agent 配置 ─────────────────────────────────────────────────
MAX_TURNS = 8  # 最大推理轮次（4 个工具 + 缓冲）

# ── Agent 系统提示词 ───────────────────────────────────────────
STU_ANALYSIS_SYSTEM_PROMPT = """你是一位专业的 408 学习分析师。你的任务是对学生现阶段学习情况进行全面的学习分析。

## 你的能力

你可以使用以下四个工具来收集学生数据：

| 工具 | 用途 | 何时使用 |
|------|------|----------|
| query_student_level | 查询学生综合评级（A/B/C/D/E） | 分析开始阶段，了解学生整体定位 |
| query_knowledge_mastery | 查询各知识点掌握度（0-5分） | 了解学生在哪些知识点上强/弱 |
| query_wrong_exercises | 查询错题记录列表 | 了解学生在实际做题中暴露的问题 |
| query_wrong_knowledge_summary | 统计错题在各知识点的分布 | 识别反复出错的知识领域 |

## 工作方式

你需要**自主决定**分析策略，而不是按照固定流程：

1. **主动收集数据** — 根据分析需要，自行决定调用哪些工具、以什么顺序调用
2. **观察结果** — 仔细阅读每个工具返回的数据，判断数据是否充足
3. **动态调整** — 如果某个维度数据缺失，如实记录并基于可用数据继续分析
4. **综合诊断** — 将所有观察结果关联起来，找出根本问题（例如：某知识点掌握度低 + 该知识点错题多 = 薄弱环节确认）

## 分析框架

请从以下三个角度输出分析：

- **学习现状**：学生目前整体处于什么水平？知识掌握情况如何？
- **薄弱环节**：哪些知识点是短板？有什么证据支撑？（引用工具返回的具体数据）
- **改进建议**：针对薄弱环节，给出具体可操作的改进措施

## 评级参考

| 评级 | 含义 |
|------|------|
| A | 优秀 — 知识掌握非常扎实 |
| B | 良好 — 大部分知识掌握较好 |
| C | 中等 — 基础知识尚可，需加强薄弱环节 |
| D | 较差 — 多个知识点掌握不足，需重点突破 |
| E | 很差 — 整体基础薄弱，建议从头系统复习 |

## 最终输出格式

当你收集完足够数据后，请严格遵守以下规则输出最终结果：

1. **只输出一行纯 JSON，不要包含任何其他内容**
2. 不要输出"好的，数据已经收集完毕"之类的引言
3. 不要输出 markdown 代码块标记（```json 或 ```）
4. 不要输出任何解释、总结或后续建议
5. 你的整个回复应该就是一个 JSON 对象，以 `{` 开头，以 `}` 结尾

JSON 格式如下：
{"summary":"总体分析概述，综合所有可用维度的数据（200字以内）","weakness_analysis":"薄弱环节分析，引用具体知识点和数据（150字以内）","improvement_suggestions":"改进建议，具体可操作（150字以内）","comprehensive_rating":"综合评级（A/B/C/D/E 其中一个字母）","priority_focus":["优先改进知识点1","优先改进知识点2","优先改进知识点3"]}

## 重要提醒

- **不要**在未调用任何工具的情况下直接输出分析结果
- 如果所有工具都返回空数据，请在 summary 中如实说明"当前数据不足"
- **输出的第一个字符必须是 `{`，最后一个字符必须是 `}`**"""

# 达到最大轮次时的强制输出提示
FORCE_OUTPUT_PROMPT = (
    "你已达到最大工具调用轮次。请基于已有数据立即输出分析结果。"
    "只输出一行纯 JSON，不要包含任何引言、解释或 markdown 标记。"
    "第一个字符必须是 {，最后一个字符必须是 }。"
)


class StuAnalysisAgent:
    """学生分析 Agent — ReAct 循环 + 工具调用

    核心流程：
    1. LLM 接收系统提示 + 学生 ID
    2. ReAct 循环：Think → Act（工具调用）→ Observe（工具结果）→ Think → ...
    3. LLM 输出最终分析 JSON
    4. 后处理：从工具结果提取维度详情和权重

    Usage:
        llm = LLMClient(default_profile=deepseek_profile())
        agent = StuAnalysisAgent(llm_client=llm)
        result = await agent.analyze(stu_id=123)
    """

    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client

    # ── 公开接口 ─────────────────────────────────────────────

    async def analyze(self, stu_id: int) -> dict[str, Any]:
        """对学生进行 AI 学习分析（ReAct Agent 循环）

        这是 Agent 的唯一公开入口，返回与旧版完全兼容的结果字典。

        Args:
            stu_id: 学生 ID

        Returns:
            分析结果字典，包含 dimensions_available, weights,
            dimensions_detail, analysis, error 等字段
        """
        tools = get_stu_analysis_tool_definitions()
        tool_results: dict[str, dict[str, Any]] = {}

        # 构建初始消息
        messages: list[dict] = [
            {"role": "system", "content": STU_ANALYSIS_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"请对学生 ID={stu_id} 进行全面学习分析。"
                    f"先调用工具收集各维度的数据，再基于数据给出分析报告。"
                ),
            },
        ]

        analysis_json: dict[str, Any] | None = None
        error_msg: str | None = None

        try:
            # ReAct Agent 主循环
            for turn in range(MAX_TURNS):
                logger.debug(
                    f"[StuAnalysisAgent] Turn {turn + 1}/{MAX_TURNS}, "
                    f"stu_id={stu_id}, messages={len(messages)}"
                )

                response = await self.llm.chat(
                    messages,
                    tools=tools,
                    temperature=0.5,
                )

                # ── 分支 1: LLM 请求调用工具 ──
                if response.tool_calls:
                    # 记录 assistant 消息（包含 tool_calls）
                    messages.append(self._build_assistant_message(response))

                    # 执行每个工具，收集 Observation
                    for tc in response.tool_calls:
                        logger.info(
                            f"[StuAnalysisAgent] LLM 调用工具: {tc.name}, "
                            f"stu_id={stu_id}"
                        )
                        result = execute_analysis_tool(tc.name, stu_id)
                        tool_results[tc.name] = result

                        # 将 Observation 追加到消息历史
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": json.dumps(result, ensure_ascii=False, default=str),
                        })

                    # 继续循环 → LLM 观察结果后决定下一步
                    continue

                # ── 分支 2: LLM 给出最终答案 ──
                if response.content:
                    analysis_json = self._parse_analysis_json(response.content)
                    logger.info(
                        f"[StuAnalysisAgent] Agent 完成分析, "
                        f"stu_id={stu_id}, turns={turn + 1}"
                    )
                    break

                # ── 分支 3: 既无工具调用也无内容（异常） ──
                logger.warning(
                    f"[StuAnalysisAgent] 第 {turn + 1} 轮 LLM 返回为空, stu_id={stu_id}"
                )
                break

            else:
                # ── 达到最大轮次，强制要求输出 ──
                logger.warning(
                    f"[StuAnalysisAgent] 达到最大轮次 {MAX_TURNS}, "
                    f"强制输出, stu_id={stu_id}"
                )
                messages.append({
                    "role": "system",
                    "content": FORCE_OUTPUT_PROMPT,
                })
                final_response = await self.llm.chat(messages, temperature=0.7)
                if final_response.content:
                    analysis_json = self._parse_analysis_json(final_response.content)

        except Exception as e:
            logger.error(
                f"[StuAnalysisAgent] Agent 循环异常 stu_id={stu_id}: {e}",
                exc_info=True,
            )
            error_msg = f"AI 分析生成失败: {str(e)}"

        # ═══════════════════════════════════════════════════════
        # 后处理：从工具结果提取结构化维度详情
        # （这些是确定性计算，不应由 LLM 完成）
        # ═══════════════════════════════════════════════════════
        dimensions_detail = self._build_dimensions_detail(tool_results)
        available_count = sum(
            1 for v in dimensions_detail.values() if v.get("available", False)
        )
        weights = self._compute_weights(dimensions_detail, available_count)

        # 确定错误信息（优先级：Agent 异常 > 数据全部缺失 > 无错误）
        if error_msg:
            pass  # Agent 循环中已记录异常
        elif available_count == 0:
            error_msg = "所有维度数据均缺失，无法生成分析报告"

        return {
            "stu_id": stu_id,
            "dimensions_available": available_count,
            "weights": weights,
            "dimensions_detail": dimensions_detail,
            "analysis": analysis_json,
            # error 只在有错误时为字符串，否则为 None
            # 前端通过 if (result.error) 判断 — null 为 falsy
            "error": error_msg,
        }

    # ── 内部方法 ─────────────────────────────────────────────

    @staticmethod
    def _build_assistant_message(response) -> dict:
        """将 LLM 响应中的 tool_calls 构建为 OpenAI 格式的 assistant 消息"""
        return {
            "role": "assistant",
            "content": response.content or None,
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": json.dumps(tc.arguments, ensure_ascii=False),
                    },
                }
                for tc in response.tool_calls
            ],
        }

    @staticmethod
    def _parse_analysis_json(text: str) -> dict[str, Any]:
        """解析 LLM 输出的分析 JSON，带多层容错处理

        按优先级尝试：
        1. 纯 JSON 字符串（以 { 开头）
        2. 包裹在 ```json ... ``` 中的 JSON
        3. 包裹在 ``` ... ``` 中的 JSON
        4. 文本中夹杂的 JSON（以第一个 { 到最后一个 } 提取）
        """
        text = text.strip()

        # 尝试 1: 直接解析（正常情况 — LLM 遵守了指令）
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # 尝试 2: 从 ```json ... ``` 代码块中提取
        if "```json" in text:
            try:
                json_str = text.split("```json")[1].split("```")[0].strip()
                return json.loads(json_str)
            except (json.JSONDecodeError, IndexError):
                pass

        # 尝试 3: 从 ``` ... ``` 代码块中提取
        if "```" in text:
            try:
                json_str = text.split("```")[1].split("```")[0].strip()
                return json.loads(json_str)
            except (json.JSONDecodeError, IndexError):
                pass

        # 尝试 4: 文本中嵌入的 JSON（LLM 在 JSON 前/后加了闲聊文字）
        # 找到第一个 { 和最后一个 }，尝试提取中间的 JSON
        first_brace = text.find("{")
        last_brace = text.rfind("}")
        if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
            try:
                json_str = text[first_brace:last_brace + 1]
                return json.loads(json_str)
            except json.JSONDecodeError:
                pass

        # 兜底：返回原始文本
        logger.warning(
            f"[StuAnalysisAgent] 无法解析 LLM 输出为 JSON: {text[:200]}..."
        )
        return {"raw_response": text}

    @staticmethod
    def _build_dimensions_detail(
        tool_results: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        """从工具执行结果中构建维度详情（确定性后处理）

        从工具返回的 data 字段中提取结构化信息，
        不依赖 LLM 输出，确保维度判定的一致性。
        """
        detail: dict[str, Any] = {
            "level": {"available": False, "value": None},
            "mastery": {"available": False, "node_count": 0, "weakest_nodes": []},
            "wrong_exercises": {
                "available": False,
                "total_count": 0,
                "knowledge_summary": [],
            },
        }

        # ── 维度 1: 学生评级 ──
        level_result = tool_results.get("query_student_level", {})
        level_data = level_result.get("data", {}) if level_result else {}
        if level_data.get("level"):
            detail["level"] = {
                "available": True,
                "value": level_data["level"],
            }

        # ── 维度 2: 知识图谱掌握度 ──
        mastery_result = tool_results.get("query_knowledge_mastery", {})
        mastery_data = mastery_result.get("data", {}) if mastery_result else {}
        nodes = mastery_data.get("nodes", [])
        if nodes:
            detail["mastery"] = {
                "available": True,
                "node_count": len(nodes),
                "weakest_nodes": [
                    {"name": n.get("kg_node_name", "未知"), "degree": n.get("kg_degree", 0)}
                    for n in sorted(nodes, key=lambda x: x.get("kg_degree", 5))[:5]
                ],
            }

        # ── 维度 3: 错题记录 + 知识点分布 ──
        wrong_result = tool_results.get("query_wrong_exercises", {})
        wrong_data = wrong_result.get("data", {}) if wrong_result else {}
        exercises = wrong_data.get("exercises", [])

        summary_result = tool_results.get("query_wrong_knowledge_summary", {})
        summary_data = summary_result.get("data", {}) if summary_result else {}
        knowledge_summary = summary_data.get("summary", [])

        if exercises or knowledge_summary:
            detail["wrong_exercises"] = {
                "available": True,
                "total_count": len(exercises),
                "knowledge_summary": [
                    {
                        "node": k.get("kg_node_name") or "未知",
                        "wrong_count": k.get("wrong_count", 0),
                        "avg_score": k.get("avg_score"),
                    }
                    for k in knowledge_summary
                ],
            }

        return detail

    @staticmethod
    def _compute_weights(
        dimensions_detail: dict[str, Any],
        available_count: int,
    ) -> dict[str, float]:
        """根据可用维度计算权重（等权分配）"""
        if available_count == 0:
            return {"level": 0.0, "mastery": 0.0, "wrong_exercises": 0.0}

        weight = 1.0 / available_count
        return {
            "level": weight if dimensions_detail["level"]["available"] else 0.0,
            "mastery": weight if dimensions_detail["mastery"]["available"] else 0.0,
            "wrong_exercises": (
                weight if dimensions_detail["wrong_exercises"]["available"] else 0.0
            ),
        }

# 便捷函数（保持向后兼容）
async def analyze_student(stu_id: int) -> dict[str, Any]:
    """对学生进行 AI 学习分析（便捷函数，保持向后兼容）

    内部使用 StuAnalysisAgent（ReAct Agent）替代旧版工作流。

    Args:
        stu_id: 学生 ID

    Returns:
        分析结果字典，格式与旧版完全兼容
    """
    llm = LLMClient(default_profile=deepseek_profile())
    agent = StuAnalysisAgent(llm_client=llm)
    return await agent.analyze(stu_id)
