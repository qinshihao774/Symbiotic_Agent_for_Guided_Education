"""教师建议与评价专职 Agent — 基于 ReAct + Observation 循环，为教师生成对单个学生的建议与评价

===== ReAct Agent 循环 =====

  ┌──────────┐    工具调用     ┌──────────┐
  │   LLM    │ ──────────────→ │  工具执行  │
  │ 推理+决策 │ ←────────────── │ (DB查询)  │
  └──────────┘    Observation  └──────────┘
       │
       │ 最终答案
       ▼
  结构化评价 JSON

===== 评估维度（两个维度） =====

教师对单个学生的建议与评价，严格基于以下两个维度综合评估：

1. **当下学科的知识图谱进度**（知识图谱进度维度）
   - 知识点掌握程度（query_student_knowledge_mastery）
   - 学科掌握程度（query_student_course_mastery）

2. **学生的 AI 评级**（query_student_level，students.stu_level）

===== 工具动态发现与调用 =====

本 Agent 不绑定固定工作流。三个工具（query_student_level / query_student_knowledge_mastery /
query_student_course_mastery）通过 OpenAI function-calling 格式注册给 LLM，
由 LLM 在 ReAct 循环中**自主决定**调用哪些工具、以什么顺序调用、调用几次。

===== 输出格式（与前端兼容） =====

返回的 dict 结构如下：
{
    "stu_id": int,
    "course_id": int,
    "course_name": str | None,
    "status": "ok" | "insufficient" | "db_error",
    "dimensions_available": int (0-2),
    "weights": {"level": float, "knowledge_mastery": float, "course_mastery": float},
    "dimensions_detail": {
        "level": {"available": bool, "value": str|None},
        "knowledge_mastery": {"available": bool, "node_count": int, "weakest_nodes": [...]},
        "course_mastery": {"available": bool, "course_degree": float|None, "course_process": float|None}
    },
    "missing_dimensions": [str],
    "error": str | None,
    "error_message": str | None,
    "evaluation": {...} | None
}
"""
import json
import logging
from typing import Any

from app.agent.tools.stu_evaluation_db import (
    execute_stu_evaluation_tool,
    get_stu_evaluation_tool_definitions,
)
from app.engines.llm.client import LLMClient
from app.engines.llm.profiles import deepseek_profile

logger = logging.getLogger(__name__)

# ── Agent 配置 ─────────────────────────────────────────────────
MAX_TURNS = 8  # 最大推理轮次（3 个工具 + 缓冲）
TEMPERATURE = 0.2  # 教师建议与评价要求稳定、客观，temperature 固定为 0.2

# 两个评估维度的固定标识（用于权重计算与缺失判定）
DIMENSION_KEYS = ["level", "knowledge_mastery", "course_mastery"]
DIMENSION_LABELS = {
    "level": "学生 AI 评级",
    "knowledge_mastery": "知识点掌握程度",
    "course_mastery": "学科掌握程度",
}

# 工具名 → 维度 key 的映射
_TOOL_TO_DIMENSION = {
    "query_student_level": "level",
    "query_student_knowledge_mastery": "knowledge_mastery",
    "query_student_course_mastery": "course_mastery",
}


# ── 数据采集系统提示词（ReAct 循环用）──────────────────────────
DATA_COLLECTION_SYSTEM_PROMPT = """你是一位教师建议与评价数据采集助手。你的任务是为指定学生和学科收集生成教师建议与评价所需的两个维度数据。

## 两个评估维度

| 维度 | 工具 | 说明 |
|------|------|------|
| 学生 AI 评级 | query_student_level | 学生的综合 AI 评级（A/B/C/D/E，需 stu_id） |
| 知识图谱进度 | query_student_knowledge_mastery | 学生在某学科下各知识点的掌握度（需 stu_id + course_id） |
| 知识图谱进度 | query_student_course_mastery | 学生在某学科下的学科整体掌握度与学习进度（需 stu_id + course_id） |

## 工作方式

1. **自主决定**调用哪些工具、以什么顺序调用，不要遵循固定流程
2. 观察每个工具返回的结果，判断数据是否充足
3. 如果某个工具返回"暂无数据"或"数据库异常"，如实记录，不要臆造数据
4. 收集完所需数据后，输出一行纯 JSON 表示"数据收集完成"

## 输出格式

当你收集完数据后，只输出一行纯 JSON：
{"status":"collected","collected":["level","knowledge_mastery","course_mastery"]}

不要输出任何其他内容、解释或 markdown 标记。"""


# ── 评价生成系统提示词（两个维度综合评估）──────────────────────
def build_evaluation_system_prompt() -> str:
    """构建评价生成阶段的系统提示词（约束两个维度综合评估）"""
    return """你是一位资深的 408 考研学科教师。你的任务是基于单个学生的学情数据，为教师生成**具体、可执行、有针对性**的学生建议与评价。

## 评估原则

1. **两个维度综合评估**：建议与评价必须综合以下两个维度，各维度权重相等，不得偏向任何一方的片面结论：
   - **知识图谱进度**：学生在当前学科下的知识点掌握程度、学科整体掌握程度与学习进度
   - **学生 AI 评级**：学生的综合 AI 评级（A/B/C/D/E）
   若某个维度缺失，其余维度权重相应提高，但必须明确标注缺失维度。
2. **学生视角**：你面向的是单个学生，建议要能指导教师对该学生进行个性化辅导。
3. **具体可执行**：建议要具体到知识点、章节、学习策略、练习安排，而不是泛泛而谈。
4. **实事求是**：只能基于给定的数据给出评价，数据中没有的信息不得臆造。

## 输出格式

只输出一行纯 JSON，不要包含任何其他内容、解释或 markdown 标记：
{"overall_assessment":"对该学生的整体评价（综合两个维度，150字以内）","strengths":["优势1","优势2","优势3"],"weaknesses":["薄弱点1","薄弱点2","薄弱点3"],"suggestions":[{"suggestion":"建议名称","detail":"具体做法与理由"}],"priority_focus":["优先改进知识点1","优先改进知识点2","优先改进知识点3"],"teacher_notes":"给教师的补充说明（含缺失维度说明）"}"""


# ── 达到最大轮次时的强制输出提示 ───────────────────────────────
FORCE_OUTPUT_PROMPT = (
    "你已达到最大工具调用轮次。请基于已有数据立即输出数据收集完成标记。"
    "只输出一行纯 JSON：{\"status\":\"collected\",\"collected\":[...]}"
)


class StuEvaluationAgent:
    """教师建议与评价专职 Agent — ReAct 循环 + 确定性兜底

    核心流程：
    1. ReAct 循环收集两个维度数据（工具由 LLM 动态发现与调用）
    2. 确定性后处理：计算权重、判定兜底
    3. 可用维度 ≥1 时：用两个维度综合评估提示词生成建议与评价
    """

    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client

    # ── 公开接口 ─────────────────────────────────────────────

    async def generate(
        self,
        stu_id: int,
        course_id: int,
        course_name: str | None = None,
    ) -> dict[str, Any]:
        """为某学生在某学科下生成教师建议与评价（ReAct Agent 循环）

        Args:
            stu_id: 学生 ID
            course_id: 学科 ID
            course_name: 学科名称（可选，用于展示）

        Returns:
            建议与评价结果字典
        """
        course_name = course_name or f"学科{course_id}"

        # 1. ReAct 循环收集两个维度数据
        tool_results = await self._collect_dimensions(stu_id, course_id)

        # 2. 确定性后处理：构建维度详情
        dimensions_detail = self._build_dimensions_detail(tool_results)

        # 3. 兜底判定：数据库异常
        db_error_dims = [
            DIMENSION_LABELS[k]
            for k in DIMENSION_KEYS
            if dimensions_detail[k].get("error_type") == "db_error"
        ]
        if db_error_dims:
            return {
                "stu_id": stu_id,
                "course_id": course_id,
                "course_name": course_name,
                "status": "db_error",
                "dimensions_available": 0,
                "weights": self._zero_weights(),
                "dimensions_detail": dimensions_detail,
                "missing_dimensions": db_error_dims,
                "error": "db_error",
                "error_message": "数据库连接异常，暂时无法获取学生学习数据，请稍后重试。",
                "evaluation": None,
            }

        # 4. 计算可用维度与权重
        available_count = sum(
            1 for k in DIMENSION_KEYS if dimensions_detail[k].get("available", False)
        )
        weights = self._compute_weights(dimensions_detail, available_count)

        # 5. 兜底判定：可用维度 <1 → 无法评估
        if available_count < 1:
            missing = [
                DIMENSION_LABELS[k]
                for k in DIMENSION_KEYS
                if not dimensions_detail[k].get("available", False)
            ]
            return {
                "stu_id": stu_id,
                "course_id": course_id,
                "course_name": course_name,
                "status": "insufficient",
                "dimensions_available": available_count,
                "weights": weights,
                "dimensions_detail": dimensions_detail,
                "missing_dimensions": missing,
                "error": "insufficient",
                "error_message": (
                    f"当前缺失{'、'.join(missing)}维度，学生建议与评价至少需要一个维度，"
                    f"当前数据不足，暂时无法给出建议与评价。可能该学生还没有开展学习哦~"
                ),
                "evaluation": None,
            }

        # 6. 可用维度 ≥1 → 生成建议与评价
        evaluation = await self._generate_evaluation(
            stu_id, course_id, course_name, dimensions_detail, weights, available_count
        )

        return {
            "stu_id": stu_id,
            "course_id": course_id,
            "course_name": course_name,
            "status": "ok",
            "dimensions_available": available_count,
            "weights": weights,
            "dimensions_detail": dimensions_detail,
            "missing_dimensions": [],
            "error": None,
            "error_message": None,
            "evaluation": evaluation,
        }

    # ── ReAct 数据采集循环 ───────────────────────────────────

    async def _collect_dimensions(
        self,
        stu_id: int,
        course_id: int,
    ) -> dict[str, dict[str, Any]]:
        """通过 ReAct 循环收集两个维度数据

        返回 {工具名: 工具结果} 字典。循环结束后，确定性补齐
        未被 LLM 调用的维度工具，确保兜底判定有完整信息。
        """
        tools = get_stu_evaluation_tool_definitions()
        tool_results: dict[str, dict[str, Any]] = {}

        messages: list[dict] = [
            {"role": "system", "content": DATA_COLLECTION_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"请为学生 stu_id={stu_id}、学科 course_id={course_id} "
                    f"收集两个维度的数据。请自主决定调用哪些工具。"
                ),
            },
        ]

        try:
            for turn in range(MAX_TURNS):
                response = await self.llm.chat(
                    messages,
                    tools=tools,
                    temperature=TEMPERATURE,
                )

                if response.tool_calls:
                    messages.append(self._build_assistant_message(response))
                    for tc in response.tool_calls:
                        logger.info(
                            f"[StuEvaluationAgent] LLM 调用工具: {tc.name}, "
                            f"stu_id={stu_id}, course_id={course_id}"
                        )
                        args = dict(tc.arguments or {})
                        args.setdefault("stu_id", stu_id)
                        args.setdefault("course_id", course_id)
                        result = execute_stu_evaluation_tool(tc.name, args)
                        tool_results[tc.name] = result
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": json.dumps(result, ensure_ascii=False, default=str),
                        })
                    continue

                if response.content:
                    # LLM 认为数据收集完成，结束循环
                    break

                break
            else:
                # 达到最大轮次
                logger.warning(
                    f"[StuEvaluationAgent] 达到最大轮次 {MAX_TURNS}, "
                    f"stu_id={stu_id}, course_id={course_id}"
                )
        except Exception as e:
            logger.error(
                f"[StuEvaluationAgent] 数据采集循环异常 stu_id={stu_id}, "
                f"course_id={course_id}: {e}",
                exc_info=True,
            )

        # ── 确定性补齐：确保两个维度工具都被调用 ──
        # 若 LLM 漏调了某个维度工具，直接调用补齐，保证兜底判定完整
        for tool_name, dim_key in _TOOL_TO_DIMENSION.items():
            if tool_name not in tool_results:
                logger.info(
                    f"[StuEvaluationAgent] 补齐未调用工具: {tool_name}, "
                    f"stu_id={stu_id}, course_id={course_id}"
                )
                result = execute_stu_evaluation_tool(
                    tool_name,
                    {"stu_id": stu_id, "course_id": course_id},
                )
                tool_results[tool_name] = result

        return tool_results

    # ── 确定性后处理 ─────────────────────────────────────────

    @staticmethod
    def _build_dimensions_detail(
        tool_results: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        """从工具结果构建两个维度详情（确定性计算）"""
        detail: dict[str, Any] = {
            "level": {
                "available": False,
                "error_type": None,
                "value": None,
            },
            "knowledge_mastery": {
                "available": False,
                "error_type": None,
                "node_count": 0,
                "weakest_nodes": [],
            },
            "course_mastery": {
                "available": False,
                "error_type": None,
                "course_degree": None,
                "course_process": None,
            },
        }

        # ── 维度 1: 学生 AI 评级 ──
        level_result = tool_results.get("query_student_level", {})
        if level_result.get("error_type") == "db_error":
            detail["level"]["error_type"] = "db_error"
        else:
            level = level_result.get("data", {}).get("level")
            if level:
                detail["level"] = {
                    "available": True,
                    "error_type": None,
                    "value": level,
                }

        # ── 维度 2: 知识点掌握程度 ──
        mastery_result = tool_results.get("query_student_knowledge_mastery", {})
        if mastery_result.get("error_type") == "db_error":
            detail["knowledge_mastery"]["error_type"] = "db_error"
        else:
            nodes = mastery_result.get("data", {}).get("nodes", [])
            if nodes:
                detail["knowledge_mastery"] = {
                    "available": True,
                    "error_type": None,
                    "node_count": len(nodes),
                    "weakest_nodes": [
                        {
                            "name": n.get("kg_node_name", "未知"),
                            "degree": n.get("kg_degree", 0),
                        }
                        for n in sorted(nodes, key=lambda x: x.get("kg_degree", 5))[:5]
                    ],
                }

        # ── 维度 3: 学科掌握程度 ──
        course_result = tool_results.get("query_student_course_mastery", {})
        if course_result.get("error_type") == "db_error":
            detail["course_mastery"]["error_type"] = "db_error"
        else:
            course = course_result.get("data", {})
            if course.get("course_degree") is not None or course.get("course_process") is not None:
                detail["course_mastery"] = {
                    "available": True,
                    "error_type": None,
                    "course_degree": course.get("course_degree"),
                    "course_process": course.get("course_process"),
                }

        return detail

    @staticmethod
    def _compute_weights(
        dimensions_detail: dict[str, Any],
        available_count: int,
    ) -> dict[str, float]:
        """根据可用维度计算权重（等权分配，确定性计算）

        严格遵循用户要求：
        - 3 个维度可用 → 各 1/3
        - 2 个维度可用 → 各 1/2
        - 1 个维度可用 → 该维度 1.0
        """
        if available_count == 0:
            return StuEvaluationAgent._zero_weights()

        weight = round(1.0 / available_count, 4)
        return {
            k: (weight if dimensions_detail[k].get("available", False) else 0.0)
            for k in DIMENSION_KEYS
        }

    @staticmethod
    def _zero_weights() -> dict[str, float]:
        """返回全零权重"""
        return {k: 0.0 for k in DIMENSION_KEYS}

    # ── 评价生成 ─────────────────────────────────────────────

    async def _generate_evaluation(
        self,
        stu_id: int,
        course_id: int,
        course_name: str,
        dimensions_detail: dict[str, Any],
        weights: dict[str, float],
        available_count: int,
    ) -> dict[str, Any] | None:
        """用两个维度综合评估提示词生成学生建议与评价"""
        # 构建两个维度描述文本
        dimension_texts = self._build_dimension_texts(dimensions_detail)

        # 权重说明（等权，动态调整）
        weight_text = "、".join(
            f"{DIMENSION_LABELS[k]} {weights[k] * 100:.0f}%"
            for k in DIMENSION_KEYS
            if weights[k] > 0
        )
        missing_text = "、".join(
            DIMENSION_LABELS[k]
            for k in DIMENSION_KEYS
            if not dimensions_detail[k].get("available", False)
        )

        user_prompt = f"""请为学生 stu_id={stu_id} 在学科「{course_name}」(course_id={course_id}) 生成教师建议与评价。

## 两个维度数据（各维度权重相等，综合考量，不得偏向任何一方）

{chr(10).join(dimension_texts)}

## 权重分配

本次建议与评价综合以下维度，各维度权重相等：{weight_text}
{('缺失维度：' + missing_text + '（该维度无数据，其余维度权重相应提高）') if missing_text else '两个维度数据齐全，各占 1/2。'}

请基于以上数据，为该学生生成具体、可执行、有针对性、面向个性化辅导的教师建议与评价。"""

        messages: list[dict] = [
            {"role": "system", "content": build_evaluation_system_prompt()},
            {"role": "user", "content": user_prompt},
        ]

        try:
            response = await self.llm.chat(
                messages,
                temperature=TEMPERATURE,
                response_format={"type": "json_object"},
            )
            if response.content:
                evaluation = self._parse_evaluation_json(response.content)
                return evaluation
        except Exception as e:
            logger.error(
                f"[StuEvaluationAgent] 评价生成异常 stu_id={stu_id}, "
                f"course_id={course_id}: {e}",
                exc_info=True,
            )

        return None

    @staticmethod
    def _build_dimension_texts(
        dimensions_detail: dict[str, Any],
    ) -> list[str]:
        """将两个维度详情转换为可读文本（供评价提示词使用）"""
        texts: list[str] = []

        # 维度 1: 学生 AI 评级
        level = dimensions_detail.get("level", {})
        if level.get("available"):
            texts.append(
                f"【学生 AI 评级】该学生的综合 AI 评级为 {level.get('value')}。"
            )
        else:
            texts.append("【学生 AI 评级】暂无数据（可能该学生还没有评级哦~）")

        # 维度 2: 知识点掌握程度
        mastery = dimensions_detail.get("knowledge_mastery", {})
        if mastery.get("available"):
            weakest = "、".join(
                f"{n['name']}({n['degree']}/5)" for n in mastery.get("weakest_nodes", [])
            )
            texts.append(
                f"【知识点掌握程度】共 {mastery.get('node_count', 0)} 个知识点，"
                f"最薄弱知识点：{weakest}"
            )
        else:
            texts.append("【知识点掌握程度】暂无数据（可能该学生还没有开展学习哦~）")

        # 维度 3: 学科掌握程度
        course = dimensions_detail.get("course_mastery", {})
        if course.get("available"):
            degree_text = (
                f"学科整体掌握度 {course.get('course_degree')}/5"
                if course.get("course_degree") is not None
                else "学科整体掌握度暂无"
            )
            process_text = (
                f"，学科学习进度 {course.get('course_process', 0) * 100:.1f}%"
                if course.get("course_process") is not None
                else ""
            )
            texts.append(f"【学科掌握程度】{degree_text}{process_text}")
        else:
            texts.append("【学科掌握程度】暂无数据（可能该学生还没有开展学习哦~）")

        return texts

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
    def _parse_evaluation_json(text: str) -> dict[str, Any]:
        """解析 LLM 输出的评价 JSON，带多层容错处理"""
        text = text.strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        if "```json" in text:
            try:
                return json.loads(text.split("```json")[1].split("```")[0].strip())
            except (json.JSONDecodeError, IndexError):
                pass

        if "```" in text:
            try:
                return json.loads(text.split("```")[1].split("```")[0].strip())
            except (json.JSONDecodeError, IndexError):
                pass

        first_brace = text.find("{")
        last_brace = text.rfind("}")
        if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
            try:
                return json.loads(text[first_brace:last_brace + 1])
            except json.JSONDecodeError:
                pass

        logger.warning(
            f"[StuEvaluationAgent] 无法解析 LLM 输出为 JSON: {text[:200]}..."
        )
        return {"raw_response": text}


# 便捷函数（保持与 class_teaching_agent 一致的调用方式）
async def generate_stu_evaluation(
    stu_id: int,
    course_id: int,
    course_name: str | None = None,
) -> dict[str, Any]:
    """为某学生在某学科下生成教师建议与评价（便捷函数）

    Args:
        stu_id: 学生 ID
        course_id: 学科 ID
        course_name: 学科名称（可选）

    Returns:
        建议与评价结果字典
    """
    llm = LLMClient(default_profile=deepseek_profile())
    agent = StuEvaluationAgent(llm_client=llm)
    return await agent.generate(stu_id, course_id, course_name)