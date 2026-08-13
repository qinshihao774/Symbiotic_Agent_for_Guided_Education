"""AI 题目分析与解惑 Agent — 双维度深度分析

针对每一道题目，AI 分析与解惑从两个维度展开：

===== 维度 1：题目与答案深度剖析 =====
从题目题干和所有选项本身出发，深度剖析：
- 正确选项为什么对（考察的核心知识点）
- 每个错误选项为什么错（拆解错误答案对正确答案造成的知识误区）
- 学生选错时可能陷入的思维陷阱与纠正方法

===== 维度 2：GraphRAG + 知识图谱局部网络视角 =====
结合知识图谱，形成该题目涉及的局部知识点网络视角：
- 精准抽象出题目背后的中心知识点
- 遍历该学科知识图谱中中心知识点的 1 跳节点邻居
- 基于局部知识点网络进行关联分析，帮助学生建立知识体系

===== 输出格式（与前端兼容）=====

{
    "question_id": int,
    "course_id": int,
    "course_name": str | None,
    "kg_node_name": str | None,
    "status": "ok" | "no_data" | "db_error",
    "error": str | None,
    "error_message": str | None,
    "analysis": {
        "aspect1": {
            "question_type": str,
            "question_difficulty": str,
            "core_knowledge": str,          # 题目考察的核心知识点
            "correct_analysis": str,        # 正确选项深度剖析
            "misconceptions": [             # 错误选项的知识误区拆解
                {
                    "option": str,          # 选项标识（如 A/B/C/D）
                    "content": str,         # 选项内容
                    "why_wrong": str,       # 为什么错
                    "misconception": str,   # 造成的知识误区
                    "correction": str       # 如何纠正
                }
            ],
            "summary": str                  # 整体总结
        },
        "aspect2": {
            "center_node": {                # 中心知识点
                "name": str,
                "type": str,
                "description": str
            },
            "neighbors": [                  # 1 跳邻居
                {
                    "node_name": str,
                    "relationship_name": str,
                    "direction": str,
                    "node_description": str
                }
            ],
            "knowledge_network_analysis": str,  # 局部知识点网络关联分析
            "learning_suggestion": str          # 学习建议
        }
    } | None
}
"""
import json
import logging
from typing import Any

from app.agent.tools.question_analysis_db import (
    execute_question_analysis_tool,
    get_question_analysis_tool_definitions,
    query_course_name,
    query_student_answer,
)
from app.engines.llm.client import LLMClient
from app.engines.llm.profiles import deepseek_profile

logger = logging.getLogger(__name__)


# ── 分析生成系统提示词 ─────────────────────────────────────────
ANALYSIS_SYSTEM_PROMPT = """你是一位资深的 408 考研辅导老师，擅长题目深度剖析与知识图谱教学。

你的任务是对一道题目进行**深度分析与解惑**，包含三个部分：

## 个性化作答剖析（结合学生提交的答案）

针对学生提交的答案（do_stu_answer）：
1. **判定**：判断学生答案是否正确（与正确答案比对）。
2. **判定说明**：说明为什么对/为什么错。
3. **知识误区**：如果答错，精准指出学生选错时陷入的知识误区（思维陷阱）。
4. **针对性纠正**：如果答错，给出针对该学生具体错误的纠正方法。
如果学生未作答或未提供答案，则判定为"未作答"，不强行分析。

## 维度 1：题目与答案深度剖析

从题目题干和所有选项本身出发，深度剖析：
1. **核心知识点**：精准抽象出这道题考察的核心知识点。
2. **正确选项剖析**：为什么正确选项是对的，它考察了什么。
3. **错误选项误区拆解**：针对每一个错误选项，拆解它为什么错，
   以及这个错误答案会对学生造成什么样的知识误区（思维陷阱），
   并给出如何纠正的方法。
4. **整体总结**：用通俗易懂的语言总结这道题的关键。

## 维度 2：GraphRAG + 知识图谱局部网络视角

结合知识图谱提供的局部知识点网络（中心知识点 + 1 跳邻居）：
1. **知识网络关联分析**：分析中心知识点与 1 跳邻居之间的关联，
   说明这些知识点如何共同构成一个知识体系，以及它们与本题的关系。
2. **学习建议**：基于局部知识点网络，给出针对性的学习建议，
   帮助学生举一反三、建立知识体系。

## 原则

- 实事求是：只能基于给定的题目数据、学生答案和知识图谱数据进行分析，
  数据中没有的信息不得臆造。
- 深度剖析：不要泛泛而谈，要具体到知识点、误区、纠正方法。
- 通俗易懂：面向学生，语言要清晰、有教学性。
- 个性化作答剖析要结合学生实际提交的答案，答对时给予肯定，答错时精准纠偏。

## 输出格式

只输出一行纯 JSON，不要包含任何其他内容、解释或 markdown 标记：
{"personal":{"stu_answer":"学生答案","is_correct":true,"verdict":"判定说明","personal_misconception":"答错时的知识误区（答对或未作答可为空字符串）","personal_correction":"答错时的针对性纠正（答对或未作答可为空字符串）"},"aspect1":{"question_type":"题型","question_difficulty":"难度","core_knowledge":"核心知识点","correct_analysis":"正确选项剖析","misconceptions":[{"option":"A","content":"选项内容","why_wrong":"为什么错","misconception":"造成的知识误区","correction":"如何纠正"}],"summary":"整体总结"},"aspect2":{"center_node":{"name":"中心知识点","type":"类型","description":"描述"},"neighbors":[{"node_name":"邻居知识点","relationship_name":"关系","direction":"out/in","node_description":"描述"}],"knowledge_network_analysis":"局部知识点网络关联分析","learning_suggestion":"学习建议"}}"""


class QuestionAnalysisAgent:
    """AI 题目分析与解惑 Agent

    核心流程：
    1. 确定性查询题目数据（query_question）
    2. 确定性查询知识图谱局部网络视角（query_graph_context）
    3. 兜底判定（db_error / no_data）
    4. 用双维度提示词生成深度分析
    """

    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client

    # ── 公开接口 ─────────────────────────────────────────────

    async def analyze(
        self,
        question_id: int,
        do_stu_answer: str | None = None,
        stu_id: int | None = None,
    ) -> dict[str, Any]:
        """对指定题目进行 AI 分析与解惑

        Args:
            question_id: 题目 ID
            do_stu_answer: 学生提交的答案（do_stu_answer），用于个性化作答剖析
            stu_id: 学生 ID，可选，用于前端未传答案时兜底查询最近一次作答

        Returns:
            分析结果字典（含个性化作答剖析 + 双维度 analysis）
        """
        # ── Phase 1: 确定性查询题目数据 ──
        question_result = execute_question_analysis_tool(
            "query_question", {"question_id": question_id}
        )
        if question_result.get("error_type") == "db_error":
            return {
                "question_id": question_id,
                "course_id": None,
                "course_name": None,
                "kg_node_name": None,
                "status": "db_error",
                "error": "db_error",
                "error_message": "数据库连接异常，暂时无法获取题目数据，请稍后重试。",
                "analysis": None,
            }
        if question_result.get("error_type") == "no_data":
            return {
                "question_id": question_id,
                "course_id": None,
                "course_name": None,
                "kg_node_name": None,
                "status": "no_data",
                "error": "no_data",
                "error_message": f"题目 {question_id} 不存在，无法进行分析。",
                "analysis": None,
            }

        question = question_result.get("data", {}).get("question", {})
        course_id = question.get("course_id")
        kg_node_name = question.get("kg_node_name")

        # 查询学科名称（供展示）
        course_name = None
        if course_id:
            try:
                course_name = query_course_name(course_id)
            except Exception as e:
                logger.warning(f"查询学科名称失败 (course_id={course_id}): {e}")

        # ── Phase 1.5: 解析学生答案（个性化作答剖析） ──
        # 优先使用前端传入的答案；未传入且提供了 stu_id 时，兜底查询最近一次作答
        stu_answer = do_stu_answer
        if not stu_answer and stu_id:
            try:
                stu_answer = query_student_answer(stu_id, question_id)
            except Exception as e:
                logger.warning(
                    f"查询学生作答失败 (stu_id={stu_id}, question_id={question_id}): {e}"
                )

        # ── Phase 2: 确定性查询知识图谱局部网络视角 ──
        graph_result = None
        if course_id and kg_node_name:
            graph_result = execute_question_analysis_tool(
                "query_graph_context",
                {"course_id": course_id, "kg_node_name": kg_node_name},
            )

        # ── Phase 3: 兜底判定 ──
        # 题目数据已获取，但图谱视角可能缺失（no_data / db_error）
        # 图谱缺失不阻断整体分析，仅影响维度 2 的深度
        graph_context = None
        graph_error = None
        if graph_result:
            if graph_result.get("error_type") == "db_error":
                graph_error = graph_result.get("summary")
                logger.warning(
                    f"[QuestionAnalysisAgent] 图谱视角 db_error: {graph_error}"
                )
            elif graph_result.get("error_type") == "no_data":
                graph_error = graph_result.get("summary")
                logger.info(
                    f"[QuestionAnalysisAgent] 图谱视角 no_data: {graph_error}"
                )
            else:
                graph_context = graph_result.get("data", {}).get("graph_context")

        # ── Phase 4: 生成深度分析（个性化作答剖析 + 双维度） ──
        analysis = await self._generate_analysis(
            question, graph_context, graph_error, stu_answer
        )

        return {
            "question_id": question_id,
            "course_id": course_id,
            "course_name": course_name,
            "kg_node_name": kg_node_name,
            "status": "ok",
            "error": None,
            "error_message": None,
            "analysis": analysis,
        }

    # ── 分析生成 ─────────────────────────────────────────────

    async def _generate_analysis(
        self,
        question: dict[str, Any],
        graph_context: dict[str, Any] | None,
        graph_error: str | None,
        stu_answer: str | None = None,
    ) -> dict[str, Any] | None:
        """用提示词生成深度分析（个性化作答剖析 + 双维度）"""
        # 构建题目描述文本
        question_text = self._build_question_text(question)

        # 构建图谱视角文本
        graph_text = self._build_graph_text(graph_context, graph_error)

        # 学生答案文本
        stu_answer_text = stu_answer if stu_answer else "（学生未作答或未提供答案）"

        user_prompt = f"""请对以下题目进行深度分析与解惑。

## 题目数据

{question_text}

## 学生提交的答案

{stu_answer_text}

## 知识图谱局部网络视角

{graph_text}

请基于以上数据，从「个性化作答剖析」「题目与答案深度剖析」和「GraphRAG + 知识图谱局部网络视角」三个部分进行分析。"""

        messages: list[dict] = [
            {"role": "system", "content": ANALYSIS_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        try:
            response = await self.llm.chat(
                messages,
                temperature=0.8,
                response_format={"type": "json_object"},
            )
            if response.content:
                analysis = self._parse_analysis_json(response.content)
                return analysis
        except Exception as e:
            logger.error(
                f"[QuestionAnalysisAgent] 分析生成异常 question_id={question.get('question_id')}: {e}",
                exc_info=True,
            )

        return None

    @staticmethod
    def _build_question_text(question: dict[str, Any]) -> str:
        """将题目数据转换为可读文本"""
        lines: list[str] = []
        lines.append(f"- 题型：{question.get('question_type', '未知')}")
        lines.append(f"- 难度：{question.get('question_difficulty', '未知')}")
        lines.append(f"- 题干：{question.get('question_description', '')}")
        lines.append(f"- 正确答案：{question.get('question_answer', '')}")

        # 选项（兼容 dict 与 list 两种格式）
        options = question.get("question_options")
        if options:
            lines.append("- 选项：")
            if isinstance(options, dict):
                for key, value in options.items():
                    lines.append(f"  - {key}. {value}")
            elif isinstance(options, list):
                labels = ["A", "B", "C", "D", "E", "F", "G", "H"]
                for idx, opt in enumerate(options):
                    label = labels[idx] if idx < len(labels) else str(idx + 1)
                    lines.append(f"  - {label}. {opt}")
        else:
            lines.append("- 选项：无")

        if question.get("question_explanation"):
            lines.append(f"- 解析：{question.get('question_explanation')}")

        return "\n".join(lines)

    @staticmethod
    def _build_graph_text(
        graph_context: dict[str, Any] | None,
        graph_error: str | None,
    ) -> str:
        """将知识图谱局部网络视角转换为可读文本"""
        if graph_error:
            return f"（知识图谱局部网络视角暂不可用：{graph_error}）"

        if not graph_context:
            return "（该题目未关联知识图谱，无法进行图谱视角分析）"

        lines: list[str] = []
        center = graph_context.get("center_node", {})
        lines.append(f"- 中心知识点：{center.get('name', '未知')}（类型：{center.get('type', 'Concept')}）")
        if center.get("description"):
            lines.append(f"- 中心知识点描述：{center.get('description')}")

        neighbors = graph_context.get("neighbors", [])
        if neighbors:
            lines.append(f"- 1 跳邻居（共 {len(neighbors)} 个）：")
            for nb in neighbors:
                arrow = "→" if nb.get("direction") == "out" else "←"
                desc = nb.get("node_description") or ""
                lines.append(
                    f"  - {nb.get('node_name', '未知')} {arrow} "
                    f"关系「{nb.get('relationship_name', 'related_to')}」"
                    + (f"：{desc}" if desc else "")
                )
        else:
            lines.append("- 该中心知识点暂无 1 跳邻居。")

        return "\n".join(lines)

    @staticmethod
    def _parse_analysis_json(text: str) -> dict[str, Any]:
        """解析 LLM 输出的分析 JSON，带多层容错处理"""
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
            f"[QuestionAnalysisAgent] 无法解析 LLM 输出为 JSON: {text[:200]}..."
        )
        return {"raw_response": text}


# 便捷函数
async def analyze_question(
    question_id: int,
    do_stu_answer: str | None = None,
    stu_id: int | None = None,
) -> dict[str, Any]:
    """对指定题目进行 AI 分析与解惑（便捷函数）

    Args:
        question_id: 题目 ID
        do_stu_answer: 学生提交的答案（do_stu_answer），用于个性化作答剖析
        stu_id: 学生 ID，可选，用于前端未传答案时兜底查询最近一次作答

    Returns:
        分析结果字典
    """
    llm = LLMClient(default_profile=deepseek_profile())
    agent = QuestionAnalysisAgent(llm_client=llm)
    return await agent.analyze(
        question_id,
        do_stu_answer=do_stu_answer,
        stu_id=stu_id,
    )
