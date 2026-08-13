"""班级教学建议 Agent — 基于 ReAct + Observation 循环，为教师生成班级教学建议

===== 核心设计 =====

班级教学建议必须**综合班级整体数据**，从三个维度评估班级学情并给出下一步教学建议。

三个维度（各占 1/3 权重，动态调整）：
1. 学生评级分布       (students.stu_level，按班级聚合)
2. 班级知识点平均掌握度进度 (student_knowledge_mastery / student_course_mastery，按班级聚合)
3. 疑难章节与知识点   (exercise_records 错题，按班级聚合；疑难章节与知识点视为同一维度)

===== 兜底机制（确定性计算，不交给 LLM）=====

每个维度查询结果分三种状态：
- 有数据（success=True, error_type=None）
- 无数据（success=False, error_type="no_data"）→ 前端提示"可能该班级还没有开展学习哦~"
- 数据库异常（success=False, error_type="db_error"）→ 前端显示用户友好错误

权重动态计算（严格遵循用户要求）：
- 3 个维度可用 → 各 1/3
- 2 个维度可用（缺 1 个）→ 各 1/2，仍执行评估
- <2 个维度可用 → 无法评估，前端友好提示缺失维度及原因

===== 输出格式（与前端兼容）=====

{
    "class_id": int,
    "course_id": int,
    "course_name": str,
    "status": "ok" | "insufficient" | "db_error",
    "dimensions_available": int,
    "weights": {...},
    "dimensions_detail": {...},
    "missing_dimensions": [str],
    "error": str | None,
    "error_message": str | None,
    "suggestion": {...} | None
}
"""
import json
import logging
from typing import Any

from app.agent.tools.class_teaching_db import (
    execute_class_teaching_tool,
    get_class_teaching_tool_definitions,
)
from app.engines.llm.client import LLMClient
from app.engines.llm.profiles import deepseek_profile

logger = logging.getLogger(__name__)

# ── Agent 配置 ─────────────────────────────────────────────────
MAX_TURNS = 10  # 最大推理轮次（3 个工具 + 缓冲）

# 三个维度的固定标识（用于权重计算与缺失判定）
DIMENSION_KEYS = ["student_level", "class_mastery", "difficult"]
DIMENSION_LABELS = {
    "student_level": "学生评级",
    "class_mastery": "班级知识点平均掌握度进度",
    "difficult": "疑难章节与知识点",
}

# 工具名 → 维度 key 的映射
_TOOL_TO_DIMENSION = {
    "query_class_students": "student_level",
    "query_class_mastery": "class_mastery",
    "query_class_difficult": "difficult",
}


# ── 数据采集系统提示词（ReAct 循环用）──────────────────────────
DATA_COLLECTION_SYSTEM_PROMPT = """你是一位班级教学建议数据采集助手。你的任务是为指定班级和学科收集生成教学建议所需的三个维度数据。

## 三个维度

| 维度 | 工具 | 说明 |
|------|------|------|
| 学生评级 | query_class_students | 班级内所有学生的评级分布（students.stu_level，需 class_id） |
| 班级知识点平均掌握度进度 | query_class_mastery | 班级在某学科下的知识点平均掌握度与整体进度（需 class_id + course_id） |
| 疑难章节与知识点 | query_class_difficult | 班级在某学科下的疑难章节与知识点分布（错题聚合，需 class_id + course_id） |

## 工作方式

1. **必须调用全部三个维度工具**，为当前班级和学科收集完整数据
2. 观察每个工具返回的结果，判断数据是否充足
3. 如果某个工具返回"暂无数据"或"数据库异常"，如实记录，不要臆造数据
4. 收集完三个维度后，输出一行纯 JSON 表示"数据收集完成"

## 输出格式

当你收集完三个维度数据后，只输出一行纯 JSON：
{"status":"collected","collected":["student_level","class_mastery","difficult"]}

不要输出任何其他内容、解释或 markdown 标记。"""


# ── 建议生成系统提示词（权重约束）──────────────────────────────
def build_suggestion_system_prompt() -> str:
    """构建建议生成阶段的系统提示词（约束三维度权重）"""
    return """你是一位资深的 408 考研班级教学顾问。你的任务是基于班级整体学情数据，为教师生成**具体、可执行、有针对性**的下一步教学建议。

## 建议原则

1. **三维度等权约束**：建议必须综合三个维度（学生评级、班级知识点平均掌握度进度、疑难章节与知识点），各维度权重相等，**不得偏向任何一方的片面结论**。若某个维度缺失，其余维度权重相应提高，但必须明确标注缺失维度。
2. **班级视角**：你面向的是整个班级，而不是单个学生。建议要能指导教师在课堂上统一施教。
3. **具体可执行**：建议要具体到章节、知识点、教学策略、练习安排，而不是泛泛而谈。
4. **实事求是**：只能基于给定的数据给出建议，数据中没有的信息不得臆造。

## 输出格式

只输出一行纯 JSON，不要包含任何其他内容、解释或 markdown 标记：
{"overall_assessment":"班级整体学情评估（150字以内）","priority_focus":["优先教学重点1","优先教学重点2","优先教学重点3"],"teaching_strategies":[{"strategy":"教学策略名称","detail":"具体做法与理由"}],"difficult_focus":"针对疑难章节与知识点的专项突破建议","homework_suggestion":"作业与练习安排建议","teacher_notes":"给教师的补充说明（含缺失维度说明）"}"""


# ── 达到最大轮次时的强制输出提示 ───────────────────────────────
FORCE_OUTPUT_PROMPT = (
    "你已达到最大工具调用轮次。请基于已有数据立即输出数据收集完成标记。"
    "只输出一行纯 JSON：{\"status\":\"collected\",\"collected\":[...]}"
)


class ClassTeachingAgent:
    """班级教学建议 Agent — ReAct 循环 + 确定性兜底

    核心流程：
    1. ReAct 循环收集三维度数据
    2. 确定性后处理：计算权重、判定兜底
    3. 可用维度 ≥2 时：用权重约束提示词生成教学建议
    """

    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client

    # ── 公开接口 ─────────────────────────────────────────────

    async def generate(
        self,
        class_id: int,
        course_id: int,
        course_name: str | None = None,
    ) -> dict[str, Any]:
        """为某班级在某学科下生成教学建议（ReAct Agent 循环）

        Args:
            class_id: 班级 ID
            course_id: 学科 ID
            course_name: 学科名称（可选，用于展示）

        Returns:
            教学建议结果字典
        """
        course_name = course_name or f"学科{course_id}"

        # 1. ReAct 循环收集三维度数据
        tool_results = await self._collect_dimensions(class_id, course_id)

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
                "class_id": class_id,
                "course_id": course_id,
                "course_name": course_name,
                "status": "db_error",
                "dimensions_available": 0,
                "weights": self._zero_weights(),
                "dimensions_detail": dimensions_detail,
                "missing_dimensions": db_error_dims,
                "error": "db_error",
                "error_message": "数据库连接异常，暂时无法获取班级学习数据，请稍后重试。",
                "suggestion": None,
            }

        # 4. 计算可用维度与权重
        available_count = sum(
            1 for k in DIMENSION_KEYS if dimensions_detail[k].get("available", False)
        )
        weights = self._compute_weights(dimensions_detail, available_count)

        # 5. 兜底判定：可用维度 <2 → 无法评估
        if available_count < 2:
            available_labels = [
                DIMENSION_LABELS[k]
                for k in DIMENSION_KEYS
                if dimensions_detail[k].get("available", False)
            ]
            missing = [
                DIMENSION_LABELS[k]
                for k in DIMENSION_KEYS
                if not dimensions_detail[k].get("available", False)
            ]
            return {
                "class_id": class_id,
                "course_id": course_id,
                "course_name": course_name,
                "status": "insufficient",
                "dimensions_available": available_count,
                "weights": weights,
                "dimensions_detail": dimensions_detail,
                "missing_dimensions": missing,
                "error": "insufficient",
                "error_message": (
                    f"当前仅具备{'、'.join(available_labels) if available_labels else '无'}维度，"
                    f"缺失{'、'.join(missing)}维度。班级教学评估至少需要两个维度，"
                    f"当前数据不足，暂时无法给出教学建议。"
                ),
                "suggestion": None,
            }

        # 6. 可用维度 ≥2 → 生成教学建议
        suggestion = await self._generate_suggestion(
            class_id, course_id, course_name, dimensions_detail, weights, available_count
        )

        return {
            "class_id": class_id,
            "course_id": course_id,
            "course_name": course_name,
            "status": "ok",
            "dimensions_available": available_count,
            "weights": weights,
            "dimensions_detail": dimensions_detail,
            "missing_dimensions": [],
            "error": None,
            "error_message": None,
            "suggestion": suggestion,
        }

    # ── ReAct 数据采集循环 ───────────────────────────────────

    async def _collect_dimensions(
        self,
        class_id: int,
        course_id: int,
    ) -> dict[str, dict[str, Any]]:
        """通过 ReAct 循环收集三维度数据

        返回 {工具名: 工具结果} 字典。循环结束后，确定性补齐
        未被 LLM 调用的维度工具，确保兜底判定有完整信息。
        """
        tools = get_class_teaching_tool_definitions()
        tool_results: dict[str, dict[str, Any]] = {}

        messages: list[dict] = [
            {"role": "system", "content": DATA_COLLECTION_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"请为班级 class_id={class_id}、学科 course_id={course_id} "
                    f"收集三个维度的数据。请依次调用三个维度工具。"
                ),
            },
        ]

        try:
            for turn in range(MAX_TURNS):
                response = await self.llm.chat(
                    messages,
                    tools=tools,
                    temperature=0.3,
                )

                if response.tool_calls:
                    messages.append(self._build_assistant_message(response))
                    for tc in response.tool_calls:
                        logger.info(
                            f"[ClassTeachingAgent] LLM 调用工具: {tc.name}, "
                            f"class_id={class_id}, course_id={course_id}"
                        )
                        args = dict(tc.arguments or {})
                        args.setdefault("class_id", class_id)
                        args.setdefault("course_id", course_id)
                        result = execute_class_teaching_tool(tc.name, args)
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
                    f"[ClassTeachingAgent] 达到最大轮次 {MAX_TURNS}, "
                    f"class_id={class_id}, course_id={course_id}"
                )
        except Exception as e:
            logger.error(
                f"[ClassTeachingAgent] 数据采集循环异常 class_id={class_id}, "
                f"course_id={course_id}: {e}",
                exc_info=True,
            )

        # ── 确定性补齐：确保三个维度工具都被调用 ──
        # 若 LLM 漏调了某个维度工具，直接调用补齐，保证兜底判定完整
        for tool_name, dim_key in _TOOL_TO_DIMENSION.items():
            if tool_name not in tool_results:
                logger.info(
                    f"[ClassTeachingAgent] 补齐未调用工具: {tool_name}, "
                    f"class_id={class_id}, course_id={course_id}"
                )
                result = execute_class_teaching_tool(
                    tool_name,
                    {"class_id": class_id, "course_id": course_id},
                )
                tool_results[tool_name] = result

        return tool_results

    # ── 确定性后处理 ─────────────────────────────────────────

    @staticmethod
    def _build_dimensions_detail(
        tool_results: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        """从工具结果构建三维度详情（确定性计算）"""
        detail: dict[str, Any] = {
            "student_level": {
                "available": False,
                "error_type": None,
                "student_count": 0,
                "level_distribution": {},
            },
            "class_mastery": {
                "available": False,
                "error_type": None,
                "avg_degree": None,
                "avg_process": None,
                "node_count": 0,
                "weakest_nodes": [],
            },
            "difficult": {
                "available": False,
                "error_type": None,
                "total_wrong": 0,
                "difficult_knowledge": [],
                "difficult_chapters": [],
            },
        }

        # ── 维度 1: 学生评级 ──
        stu_result = tool_results.get("query_class_students", {})
        if stu_result.get("error_type") == "db_error":
            detail["student_level"]["error_type"] = "db_error"
        else:
            students = stu_result.get("data", {}).get("students", [])
            if students:
                detail["student_level"] = {
                    "available": True,
                    "error_type": None,
                    "student_count": len(students),
                    "level_distribution": stu_result.get("data", {}).get("level_distribution", {}),
                }

        # ── 维度 2: 班级知识点平均掌握度进度 ──
        mastery_result = tool_results.get("query_class_mastery", {})
        if mastery_result.get("error_type") == "db_error":
            detail["class_mastery"]["error_type"] = "db_error"
        else:
            mastery = mastery_result.get("data", {})
            if mastery.get("node_count"):
                detail["class_mastery"] = {
                    "available": True,
                    "error_type": None,
                    "avg_degree": mastery.get("avg_degree"),
                    "avg_process": mastery.get("avg_process"),
                    "node_count": mastery.get("node_count", 0),
                    "weakest_nodes": mastery.get("weakest_nodes", []),
                }

        # ── 维度 3: 疑难章节与知识点 ──
        diff_result = tool_results.get("query_class_difficult", {})
        if diff_result.get("error_type") == "db_error":
            detail["difficult"]["error_type"] = "db_error"
        else:
            difficult = diff_result.get("data", {})
            if difficult.get("total_wrong"):
                detail["difficult"] = {
                    "available": True,
                    "error_type": None,
                    "total_wrong": difficult.get("total_wrong", 0),
                    "difficult_knowledge": difficult.get("difficult_knowledge", []),
                    "difficult_chapters": difficult.get("difficult_chapters", []),
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
        """
        if available_count == 0:
            return ClassTeachingAgent._zero_weights()

        weight = round(1.0 / available_count, 4)
        return {
            k: (weight if dimensions_detail[k].get("available", False) else 0.0)
            for k in DIMENSION_KEYS
        }

    @staticmethod
    def _zero_weights() -> dict[str, float]:
        """返回全零权重"""
        return {k: 0.0 for k in DIMENSION_KEYS}

    # ── 建议生成 ─────────────────────────────────────────────

    async def _generate_suggestion(
        self,
        class_id: int,
        course_id: int,
        course_name: str,
        dimensions_detail: dict[str, Any],
        weights: dict[str, float],
        available_count: int,
    ) -> dict[str, Any] | None:
        """用权重约束提示词生成班级教学建议"""
        # 构建三维度描述文本
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

        user_prompt = f"""请为班级在学科「{course_name}」(course_id={course_id}) 生成下一步教学建议。

## 三维度数据（各维度权重相等，综合考量，不得偏向任何一方）

{chr(10).join(dimension_texts)}

## 权重分配

本次教学建议综合以下维度，各维度权重相等：{weight_text}
{('缺失维度：' + missing_text + '（该维度无数据，其余维度权重相应提高）') if missing_text else '三个维度数据齐全，各占 1/3。'}

请基于以上数据，为「{course_name}」生成具体、可执行、有针对性、面向整个班级的下一步教学建议。"""

        messages: list[dict] = [
            {"role": "system", "content": build_suggestion_system_prompt()},
            {"role": "user", "content": user_prompt},
        ]

        try:
            response = await self.llm.chat(
                messages,
                temperature=0.8,
                response_format={"type": "json_object"},
            )
            if response.content:
                suggestion = self._parse_suggestion_json(response.content)
                return suggestion
        except Exception as e:
            logger.error(
                f"[ClassTeachingAgent] 建议生成异常 class_id={class_id}, "
                f"course_id={course_id}: {e}",
                exc_info=True,
            )

        return None

    @staticmethod
    def _build_dimension_texts(
        dimensions_detail: dict[str, Any],
    ) -> list[str]:
        """将三维度详情转换为可读文本（供建议提示词使用）"""
        texts: list[str] = []

        # 维度 1: 学生评级
        level = dimensions_detail.get("student_level", {})
        if level.get("available"):
            dist = "、".join(
                f"{k}级 {v}人" for k, v in level.get("level_distribution", {}).items()
            )
            texts.append(
                f"【学生评级】班级共 {level.get('student_count', 0)} 名学生，"
                f"评级分布：{dist}"
            )
        else:
            texts.append("【学生评级】暂无数据（可能该班级还没有学生哦~）")

        # 维度 2: 班级知识点平均掌握度进度
        mastery = dimensions_detail.get("class_mastery", {})
        if mastery.get("available"):
            weakest = "、".join(
                f"{n['name']}({n['avg_degree']}/5)" for n in mastery.get("weakest_nodes", [])
            )
            process_text = (
                f"，学科整体进度 {mastery.get('avg_process', 0) * 100:.1f}%"
                if mastery.get("avg_process") is not None
                else ""
            )
            texts.append(
                f"【班级知识点平均掌握度进度】共 {mastery.get('node_count', 0)} 个知识点，"
                f"平均掌握度 {mastery.get('avg_degree', 0)}/5{process_text}，"
                f"最薄弱知识点：{weakest}"
            )
        else:
            texts.append("【班级知识点平均掌握度进度】暂无数据（可能该班级还没有开展学习哦~）")

        # 维度 3: 疑难章节与知识点
        difficult = dimensions_detail.get("difficult", {})
        if difficult.get("available"):
            top = "、".join(
                f"{item['name']}(错题{item['wrong_count']}道)"
                for item in difficult.get("difficult_knowledge", [])[:5]
            )
            texts.append(
                f"【疑难章节与知识点】班级共 {difficult.get('total_wrong', 0)} 道错题，"
                f"疑难知识点 TOP：{top}"
            )
        else:
            texts.append("【疑难章节与知识点】暂无数据（可能该班级还没有开展练习哦~）")

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
    def _parse_suggestion_json(text: str) -> dict[str, Any]:
        """解析 LLM 输出的建议 JSON，带多层容错处理"""
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
            f"[ClassTeachingAgent] 无法解析 LLM 输出为 JSON: {text[:200]}..."
        )
        return {"raw_response": text}


# 便捷函数（保持与 learning_plan_agent 一致的调用方式）
async def generate_class_teaching_suggestion(
    class_id: int,
    course_id: int,
    course_name: str | None = None,
) -> dict[str, Any]:
    """为某班级在某学科下生成教学建议（便捷函数）

    Args:
        class_id: 班级 ID
        course_id: 学科 ID
        course_name: 学科名称（可选）

    Returns:
        教学建议结果字典
    """
    llm = LLMClient(default_profile=deepseek_profile())
    agent = ClassTeachingAgent(llm_client=llm)
    return await agent.generate(class_id, course_id, course_name)