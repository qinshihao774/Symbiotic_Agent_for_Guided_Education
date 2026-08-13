"""学习规划 Agent — 基于 ReAct + Observation 循环，为每门学科分别制定学习规划

===== 核心设计 =====

学习规划必须**按学科分别制定**，而不是把四门 408 科目揉在一起做总体规划。

规划依据四个维度（各占 25% 权重，动态调整）：
1. 学生端 AI 分析内容   (evaluation_analysis 中 publisher_name='AI')
2. 学生自身知识图谱     (student_knowledge_mastery，按学科 kg_id 过滤)
3. 习题情况             (exercise_records + questions，按学科 course_id 过滤：题库题目总数 + 已做题目数 → 各科进度)
4. 老师意见与评估       (evaluation_analysis 中 publisher_name != 'AI')

===== 兜底机制（确定性计算，不交给 LLM）=====

每个维度查询结果分三种状态：
- 有数据（success=True, error_type=None）
- 无数据（success=False, error_type="no_data"）→ 前端提示"可能用户还没有开展学习哦~"
- 数据库异常（success=False, error_type="db_error"）→ 前端显示用户友好错误

权重动态计算：
- 4 个维度可用 → 各 25%
- 3 个维度可用（缺 1 个）→ 各 1/3，仍执行规划
- ≤2 个维度可用 → 无法准确规划，前端提示"缺失哪一方面的维度，导致无法准确地进行学习规划！"

===== 输出格式（与前端兼容）=====

{
    "stu_id": int,
    "subjects": [
        {
            "course_id": int,
            "course_name": str,
            "status": "ok" | "insufficient" | "db_error",
            "dimensions_available": int,
            "weights": {...},
            "dimensions_detail": {...},
            "missing_dimensions": [str],
            "error": str | None,
            "plan": {...} | None
        },
        ...
    ],
    "error": str | None
}
"""
import json
import logging
from typing import Any

from app.agent.tools.learning_plan_db import (
    execute_learning_plan_tool,
    get_learning_plan_tool_definitions,
)
from app.engines.llm.client import LLMClient
from app.engines.llm.profiles import deepseek_profile

logger = logging.getLogger(__name__)

# ── Agent 配置 ─────────────────────────────────────────────────
MAX_TURNS = 10  # 最大推理轮次（5 个工具 + 缓冲）

# 四个维度的固定标识（用于权重计算与缺失判定）
DIMENSION_KEYS = ["ai_analysis", "knowledge_mastery", "exercise", "teacher_opinion"]
DIMENSION_LABELS = {
    "ai_analysis": "学生端 AI 分析内容",
    "knowledge_mastery": "学生自身知识图谱",
    "exercise": "习题情况",
    "teacher_opinion": "老师意见与评估",
}

# 工具名 → 维度 key 的映射
_TOOL_TO_DIMENSION = {
    "query_ai_analysis": "ai_analysis",
    "query_knowledge_mastery": "knowledge_mastery",
    "query_exercise_progress": "exercise",
    "query_teacher_opinion": "teacher_opinion",
}


# ── 数据采集系统提示词（ReAct 循环用）──────────────────────────
DATA_COLLECTION_SYSTEM_PROMPT = """你是一位学习规划数据采集助手。你的任务是为指定学科收集制定学习规划所需的四个维度数据。

## 四个维度

| 维度 | 工具 | 说明 |
|------|------|------|
| 学生端 AI 分析内容 | query_ai_analysis | 学生已有的 AI 学习分析 |
| 学生自身知识图谱 | query_knowledge_mastery | 各知识点掌握度（需 course_id） |
| 习题情况 | query_exercise_progress | 做题进度（题库题目总数 + 已做题目数，需 course_id） |
| 老师意见与评估 | query_teacher_opinion | 老师给出的意见与评估 |

## 工作方式

1. **必须调用全部四个维度工具**，为当前学科收集完整数据
2. 观察每个工具返回的结果，判断数据是否充足
3. 如果某个工具返回"暂无数据"或"数据库异常"，如实记录，不要臆造数据
4. 收集完四个维度后，输出一行纯 JSON 表示"数据收集完成"

## 输出格式

当你收集完四个维度数据后，只输出一行纯 JSON：
{"status":"collected","collected":["ai_analysis","knowledge_mastery","exercise","teacher_opinion"]}

不要输出任何其他内容、解释或 markdown 标记。"""


# ── 规划生成系统提示词（权重约束）──────────────────────────────
def build_plan_system_prompt() -> str:
    """构建规划生成阶段的系统提示词（约束四维度权重）"""
    return """你是一位专业的 408 考研学习规划师。你的任务是为指定学科制定**具体、细粒度、可执行**的学习规划。

## 规划原则

1. **按学科分别规划**：你只负责当前这一门学科，不要混入其他学科内容。
2. **四维度等权约束**：规划必须综合四个维度（学生端 AI 分析、知识图谱、习题情况、老师意见），各维度权重相等，**不得偏向任何一方的片面结论**。若某个维度缺失，其余维度权重相应提高，但必须明确标注缺失维度。
3. **细粒度**：规划要具体到知识点、章节、时间安排、练习量，而不是泛泛而谈。
4. **实事求是**：只能基于给定的数据制定规划，数据中没有的信息不得臆造。

## 输出格式

只输出一行纯 JSON，不要包含任何其他内容、解释或 markdown 标记：
{"overall_goal":"本学科总体学习目标（100字以内）","weak_points":["薄弱知识点1","薄弱知识点2"],"weekly_plan":[{"week":1,"theme":"本周主题","tasks":["具体任务1","具体任务2"],"exercises":"练习量建议"}],"priority_focus":["优先突破点1","优先突破点2","优先突破点3"],"teacher_notes":"结合老师意见的补充说明（若无老师意见则说明）"}"""


# ── 达到最大轮次时的强制输出提示 ───────────────────────────────
FORCE_OUTPUT_PROMPT = (
    "你已达到最大工具调用轮次。请基于已有数据立即输出数据收集完成标记。"
    "只输出一行纯 JSON：{\"status\":\"collected\",\"collected\":[...]}"
)


class LearningPlanAgent:
    """学习规划 Agent — ReAct 循环 + 确定性兜底

    核心流程：
    1. 确定性查询学科列表（courses 表全部学科）
    2. 对每门学科：ReAct 循环收集四维度数据
    3. 确定性后处理：计算权重、判定兜底
    4. 对可用维度 ≥3 的学科：用权重约束提示词生成细粒度规划
    """

    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client

    # ── 公开接口 ─────────────────────────────────────────────

    async def generate(self, stu_id: int) -> dict[str, Any]:
        """为某学生生成各学科学习规划（ReAct Agent 循环）

        Args:
            stu_id: 学生 ID

        Returns:
            学习规划结果字典（含 subjects 列表与全局 error）
        """
        # ── Phase 1: 确定性查询学科列表 ──
        subjects_result = execute_learning_plan_tool("query_subjects", {})
        if subjects_result.get("error_type") == "db_error":
            return {
                "stu_id": stu_id,
                "subjects": [],
                "error": "db_error",
                "error_message": "数据库连接异常，暂时无法获取学科列表，请稍后重试。",
            }
        if subjects_result.get("error_type") == "no_data":
            return {
                "stu_id": stu_id,
                "subjects": [],
                "error": "no_subjects",
                "error_message": "系统中暂无任何学科，无法制定学习规划。",
            }

        subjects = subjects_result.get("data", {}).get("subjects", [])
        if not subjects:
            return {
                "stu_id": stu_id,
                "subjects": [],
                "error": "no_subjects",
                "error_message": "系统中暂无任何学科，无法制定学习规划。",
            }

        # ── Phase 2: 对每门学科分别处理 ──
        subject_plans: list[dict[str, Any]] = []
        for subject in subjects:
            plan = await self._process_subject(stu_id, subject)
            subject_plans.append(plan)

        return {
            "stu_id": stu_id,
            "subjects": subject_plans,
            "error": None,
        }

    # ── 单学科处理 ───────────────────────────────────────────

    async def _process_subject(
        self,
        stu_id: int,
        subject: dict[str, Any],
    ) -> dict[str, Any]:
        """处理单门学科：收集数据 → 计算权重 → 兜底判定 → 生成规划"""
        course_id = subject.get("course_id")
        course_name = subject.get("course_name", f"学科{course_id}")

        # 1. ReAct 循环收集四维度数据
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
                "course_id": course_id,
                "course_name": course_name,
                "status": "db_error",
                "dimensions_available": 0,
                "weights": self._zero_weights(),
                "dimensions_detail": dimensions_detail,
                "missing_dimensions": db_error_dims,
                "error": "db_error",
                "error_message": "数据库连接异常，暂时无法获取学习数据，请稍后重试。",
                "plan": None,
            }

        # 4. 计算可用维度与权重
        available_count = sum(
            1 for k in DIMENSION_KEYS if dimensions_detail[k].get("available", False)
        )
        weights = self._compute_weights(dimensions_detail, available_count)

        # 5. 兜底判定：可用维度 ≤2 → 无法准确规划
        if available_count <= 2:
            missing = [
                DIMENSION_LABELS[k]
                for k in DIMENSION_KEYS
                if not dimensions_detail[k].get("available", False)
            ]
            return {
                "course_id": course_id,
                "course_name": course_name,
                "status": "insufficient",
                "dimensions_available": available_count,
                "weights": weights,
                "dimensions_detail": dimensions_detail,
                "missing_dimensions": missing,
                "error": "insufficient",
                "error_message": (
                    f"缺失{'、'.join(missing)}维度，导致无法准确地进行学习规划！"
                ),
                "plan": None,
            }

        # 6. 可用维度 ≥3 → 生成细粒度规划
        plan = await self._generate_plan(
            stu_id, subject, dimensions_detail, weights, available_count
        )

        return {
            "course_id": course_id,
            "course_name": course_name,
            "status": "ok",
            "dimensions_available": available_count,
            "weights": weights,
            "dimensions_detail": dimensions_detail,
            "missing_dimensions": [],
            "error": None,
            "plan": plan,
        }

    # ── ReAct 数据采集循环 ───────────────────────────────────

    async def _collect_dimensions(
        self,
        stu_id: int,
        course_id: int,
    ) -> dict[str, dict[str, Any]]:
        """通过 ReAct 循环收集某学科的四维度数据

        返回 {工具名: 工具结果} 字典。循环结束后，确定性补齐
        未被 LLM 调用的维度工具，确保兜底判定有完整信息。
        """
        tools = get_learning_plan_tool_definitions()
        tool_results: dict[str, dict[str, Any]] = {}

        messages: list[dict] = [
            {"role": "system", "content": DATA_COLLECTION_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"请为学科 course_id={course_id} 收集四个维度的数据。"
                    f"学生 ID={stu_id}。请依次调用四个维度工具。"
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
                            f"[LearningPlanAgent] LLM 调用工具: {tc.name}, "
                            f"stu_id={stu_id}, course_id={course_id}"
                        )
                        args = dict(tc.arguments or {})
                        args.setdefault("stu_id", stu_id)
                        args.setdefault("course_id", course_id)
                        result = execute_learning_plan_tool(tc.name, args)
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
                    f"[LearningPlanAgent] 达到最大轮次 {MAX_TURNS}, "
                    f"stu_id={stu_id}, course_id={course_id}"
                )
        except Exception as e:
            logger.error(
                f"[LearningPlanAgent] 数据采集循环异常 stu_id={stu_id}, "
                f"course_id={course_id}: {e}",
                exc_info=True,
            )

        # ── 确定性补齐：确保四个维度工具都被调用 ──
        # 若 LLM 漏调了某个维度工具，直接调用补齐，保证兜底判定完整
        for tool_name, dim_key in _TOOL_TO_DIMENSION.items():
            if tool_name not in tool_results:
                logger.info(
                    f"[LearningPlanAgent] 补齐未调用工具: {tool_name}, "
                    f"stu_id={stu_id}, course_id={course_id}"
                )
                result = execute_learning_plan_tool(
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
        """从工具结果构建四维度详情（确定性计算）"""
        detail: dict[str, Any] = {
            "ai_analysis": {"available": False, "error_type": None, "value": None},
            "knowledge_mastery": {
                "available": False,
                "error_type": None,
                "node_count": 0,
                "weakest_nodes": [],
            },
            "exercise": {
                "available": False,
                "error_type": None,
                "total_questions": 0,
                "done_count": 0,
                "progress_rate": 0.0,
            },
            "teacher_opinion": {
                "available": False,
                "error_type": None,
                "value": None,
                "publisher_name": None,
            },
        }

        # ── 维度 1: 学生端 AI 分析 ──
        ai_result = tool_results.get("query_ai_analysis", {})
        if ai_result.get("error_type") == "db_error":
            detail["ai_analysis"]["error_type"] = "db_error"
        elif ai_result.get("success") and ai_result.get("data", {}).get("ai_analysis"):
            detail["ai_analysis"] = {
                "available": True,
                "error_type": None,
                "value": ai_result["data"]["ai_analysis"],
            }

        # ── 维度 2: 知识图谱 ──
        kg_result = tool_results.get("query_knowledge_mastery", {})
        if kg_result.get("error_type") == "db_error":
            detail["knowledge_mastery"]["error_type"] = "db_error"
        else:
            nodes = kg_result.get("data", {}).get("nodes", [])
            if nodes:
                detail["knowledge_mastery"] = {
                    "available": True,
                    "error_type": None,
                    "node_count": len(nodes),
                    "weakest_nodes": [
                        {"name": n.get("kg_node_name", "未知"), "degree": n.get("kg_degree", 0)}
                        for n in sorted(nodes, key=lambda x: x.get("kg_degree", 5))[:5]
                    ],
                }

        # ── 维度 3: 习题情况 ──
        ex_result = tool_results.get("query_exercise_progress", {})
        if ex_result.get("error_type") == "db_error":
            detail["exercise"]["error_type"] = "db_error"
        else:
            progress = ex_result.get("data", {}).get("progress", {})
            done_count = progress.get("done_count") or 0
            if done_count > 0:
                detail["exercise"] = {
                    "available": True,
                    "error_type": None,
                    "total_questions": progress.get("total_questions") or 0,
                    "done_count": done_count,
                    "progress_rate": progress.get("progress_rate") or 0.0,
                }

        # ── 维度 4: 老师意见与评估 ──
        teacher_result = tool_results.get("query_teacher_opinion", {})
        if teacher_result.get("error_type") == "db_error":
            detail["teacher_opinion"]["error_type"] = "db_error"
        elif teacher_result.get("success") and teacher_result.get("data", {}).get("teacher_opinion"):
            detail["teacher_opinion"] = {
                "available": True,
                "error_type": None,
                "value": teacher_result["data"]["teacher_opinion"],
                "publisher_name": teacher_result["data"].get("publisher_name"),
            }

        return detail

    @staticmethod
    def _compute_weights(
        dimensions_detail: dict[str, Any],
        available_count: int,
    ) -> dict[str, float]:
        """根据可用维度计算权重（等权分配，确定性计算）"""
        if available_count == 0:
            return LearningPlanAgent._zero_weights()

        weight = round(1.0 / available_count, 4)
        return {
            k: (weight if dimensions_detail[k].get("available", False) else 0.0)
            for k in DIMENSION_KEYS
        }

    @staticmethod
    def _zero_weights() -> dict[str, float]:
        """返回全零权重"""
        return {k: 0.0 for k in DIMENSION_KEYS}

    # ── 规划生成 ─────────────────────────────────────────────

    async def _generate_plan(
        self,
        stu_id: int,
        subject: dict[str, Any],
        dimensions_detail: dict[str, Any],
        weights: dict[str, float],
        available_count: int,
    ) -> dict[str, Any] | None:
        """用权重约束提示词生成某学科的细粒度学习规划"""
        course_id = subject.get("course_id")
        course_name = subject.get("course_name", f"学科{course_id}")

        # 构建四维度描述文本
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

        user_prompt = f"""请为学科「{course_name}」(course_id={course_id}) 制定学习规划。

## 四维度数据（各维度权重相等，综合考量，不得偏向任何一方）

{chr(10).join(dimension_texts)}

## 权重分配

本次规划综合以下维度，各维度权重相等：{weight_text}
{('缺失维度：' + missing_text + '（该维度无数据，其余维度权重相应提高）') if missing_text else '四个维度数据齐全，各占 25%。'}

请基于以上数据，为「{course_name}」制定具体、细粒度、可执行的学习规划。"""

        messages: list[dict] = [
            {"role": "system", "content": build_plan_system_prompt()},
            {"role": "user", "content": user_prompt},
        ]

        try:
            response = await self.llm.chat(
                messages,
                temperature=0.8,
                response_format={"type": "json_object"},
            )
            if response.content:
                plan = self._parse_plan_json(response.content)
                return plan
        except Exception as e:
            logger.error(
                f"[LearningPlanAgent] 规划生成异常 stu_id={stu_id}, "
                f"course_id={course_id}: {e}",
                exc_info=True,
            )

        return None

    @staticmethod
    def _build_dimension_texts(
        dimensions_detail: dict[str, Any],
    ) -> list[str]:
        """将四维度详情转换为可读文本（供规划提示词使用）"""
        texts: list[str] = []

        # 维度 1: AI 分析
        ai = dimensions_detail.get("ai_analysis", {})
        if ai.get("available"):
            texts.append(f"【学生端 AI 分析内容】{ai.get('value', '')}")
        else:
            texts.append("【学生端 AI 分析内容】暂无数据（可能用户还没有开展学习哦~）")

        # 维度 2: 知识图谱
        kg = dimensions_detail.get("knowledge_mastery", {})
        if kg.get("available"):
            weakest = "、".join(
                f"{n['name']}({n['degree']}/5)" for n in kg.get("weakest_nodes", [])
            )
            texts.append(
                f"【学生自身知识图谱】共 {kg.get('node_count', 0)} 个知识点，"
                f"最薄弱知识点：{weakest}"
            )
        else:
            texts.append("【学生自身知识图谱】暂无数据（可能用户还没有开展学习哦~）")

        # 维度 3: 习题情况
        ex = dimensions_detail.get("exercise", {})
        if ex.get("available"):
            texts.append(
                f"【习题情况】该学科题库共 {ex.get('total_questions', 0)} 题，"
                f"已做 {ex.get('done_count', 0)} 题，"
                f"做题进度 {ex.get('progress_rate', 0) * 100:.1f}%"
            )
        else:
            texts.append("【习题情况】暂无数据（可能用户还没有开展学习哦~）")

        # 维度 4: 老师意见
        teacher = dimensions_detail.get("teacher_opinion", {})
        if teacher.get("available"):
            texts.append(
                f"【老师意见与评估】{teacher.get('value', '')}"
                f"（发布者：{teacher.get('publisher_name', '老师')}）"
            )
        else:
            texts.append("【老师意见与评估】暂无数据（可能用户还没有开展学习哦~）")

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
    def _parse_plan_json(text: str) -> dict[str, Any]:
        """解析 LLM 输出的规划 JSON，带多层容错处理"""
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
            f"[LearningPlanAgent] 无法解析 LLM 输出为 JSON: {text[:200]}..."
        )
        return {"raw_response": text}


# 便捷函数（保持与 stu_analysis_agent 一致的调用方式）
async def generate_learning_plan(stu_id: int) -> dict[str, Any]:
    """为某学生生成各学科学习规划（便捷函数）

    Args:
        stu_id: 学生 ID

    Returns:
        学习规划结果字典
    """
    llm = LLMClient(default_profile=deepseek_profile())
    agent = LearningPlanAgent(llm_client=llm)
    return await agent.generate(stu_id)
