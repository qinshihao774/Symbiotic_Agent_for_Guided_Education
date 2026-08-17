"""学生分析数据库查询工具 — 从 PostgreSQL 获取三个维度的数据

三个维度：
1. 个人知识图谱掌握度 (student_knowledge_mastery)
2. 错题记录及绑定的知识点 (exercise_records + questions)
3. 个人评级 (students.stu_level)

所有查询使用 psycopg2 直连 PostgreSQL（复用 AGE 的数据库配置）。

===== ReAct Agent 工具协议 =====

每个工具返回统一的 JSON 结构，同时服务于两个消费者：
- LLM（通过 summary 字段理解查询结果，进行下一步推理）
- 后处理代码（通过 data 字段提取结构化数据，构建 dimensions_detail）

工具返回格式：
{
    "tool": "工具名称",
    "success": true/false,
    "error_type": "db_error" | "no_data" | null,
    "data": { ... 结构化数据 ... },
    "summary": "人类可读的摘要，供 LLM 推理用"
}

error_type 说明（兜底机制核心）：
- "db_error": 数据库连接/查询异常（如连接失败、表不存在）→ 前端显示用户友好错误
- "no_data": 查询成功但该维度无内容 → 前端提示"可能用户还没有开展学习哦~"
- null:      查询成功且有数据
"""
import logging
from typing import Any

import psycopg2
import psycopg2.extras

from app.agent.tools._base import get_conn, make_json_safe, make_tool_result

logger = logging.getLogger(__name__)

# ── 评级描述（供工具返回摘要时使用）─────────────────────────────
LEVEL_DESCRIPTION = {
    "A": "优秀 — 知识掌握非常扎实",
    "B": "良好 — 大部分知识掌握较好",
    "C": "中等 — 基础知识尚可，需加强薄弱环节",
    "D": "较差 — 多个知识点掌握不足，需重点突破",
    "E": "很差 — 整体基础薄弱，建议从头系统复习",
}


# ═══════════════════════════════════════════════════════════════
# 数据库查询函数（底层，不暴露给 Agent）
# ═══════════════════════════════════════════════════════════════

def query_student_level(stu_id: int) -> str | None:
    """查询学生评级 (students.stu_level)"""
    try:
        conn = get_conn()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT stu_level FROM students WHERE stu_id = %s",
                (stu_id,),
            )
            row = cur.fetchone()
            return row[0] if row else None
    except Exception as e:
        logger.error(f"查询学生评级失败 (stu_id={stu_id}): {e}")
        raise
    finally:
        conn.close()


def query_knowledge_mastery(stu_id: int) -> list[dict[str, Any]]:
    """查询学生知识图谱掌握度 (student_knowledge_mastery)"""
    try:
        conn = get_conn()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT kg_node_name, kg_degree "
                "FROM student_knowledge_mastery "
                "WHERE stu_id = %s "
                "ORDER BY kg_degree ASC",
                (stu_id,),
            )
            rows = cur.fetchall()
            return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"查询知识图谱掌握度失败 (stu_id={stu_id}): {e}")
        raise
    finally:
        conn.close()


def query_wrong_exercises(stu_id: int, limit: int = 50) -> list[dict[str, Any]]:
    """查询学生错题记录，关联题目获取知识点"""
    try:
        conn = get_conn()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT
                    er.question_id,
                    er.kg_node_name,
                    er.question_type,
                    er.question_difficulty,
                    er.do_score,
                    er.created_at,
                    q.question_description
                FROM exercise_records er
                LEFT JOIN questions q ON er.question_id = q.question_id
                WHERE er.stu_id = %s
                  AND (er.do_istrue IS NULL OR er.do_istrue = FALSE)
                ORDER BY er.created_at DESC
                LIMIT %s
                """,
                (stu_id, limit),
            )
            rows = cur.fetchall()
            return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"查询错题记录失败 (stu_id={stu_id}): {e}")
        raise
    finally:
        conn.close()


def query_wrong_knowledge_summary(stu_id: int) -> list[dict[str, Any]]:
    """统计学生错题涉及的知识点分布"""
    try:
        conn = get_conn()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT
                    COALESCE(er.kg_node_name, q.kg_node_name) AS kg_node_name,
                    COUNT(*) AS wrong_count,
                    AVG(er.do_score) AS avg_score
                FROM exercise_records er
                LEFT JOIN questions q ON er.question_id = q.question_id
                WHERE er.stu_id = %s
                  AND (er.do_istrue IS NULL OR er.do_istrue = FALSE)
                GROUP BY COALESCE(er.kg_node_name, q.kg_node_name)
                ORDER BY wrong_count DESC
                """,
                (stu_id,),
            )
            rows = cur.fetchall()
            return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"查询错题知识点分布失败 (stu_id={stu_id}): {e}")
        raise
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════════
# ReAct Agent 工具协议层
# ═══════════════════════════════════════════════════════════════

def _build_level_result(stu_id: int) -> dict[str, Any]:
    """构建评级查询的 Agent 工具结果"""
    try:
        level = query_student_level(stu_id)
    except Exception as e:
        return make_tool_result("query_student_level", False, {"level": None},
                                f"查询学生评级时数据库连接异常: {str(e)}", "db_error")
    if not level:
        return make_tool_result("query_student_level", False, {"level": None},
                                f"学生 {stu_id} 暂无评级记录。", "no_data")
    desc = LEVEL_DESCRIPTION.get(level.upper(), "未知评级")
    return make_tool_result("query_student_level", True, {"level": level},
                            f"学生 {stu_id} 的当前评级为 {level}（{desc}）。")


def _build_mastery_result(stu_id: int) -> dict[str, Any]:
    """构建知识图谱掌握度的 Agent 工具结果"""
    try:
        nodes = query_knowledge_mastery(stu_id)
    except Exception as e:
        return make_tool_result("query_knowledge_mastery", False, {"nodes": []},
                                f"查询知识图谱掌握度时数据库连接异常: {str(e)}", "db_error")
    if not nodes:
        return make_tool_result("query_knowledge_mastery", False, {"nodes": []},
                                f"学生 {stu_id} 暂无知识图谱掌握度记录。", "no_data")

    # 构建供 LLM 阅读的摘要
    lines = [f"学生 {stu_id} 的知识图谱掌握度（共 {len(nodes)} 个知识点，按掌握度从低到高排列）："]
    for item in nodes:
        name = item.get("kg_node_name", "未知")
        degree = item.get("kg_degree", 0)
        lines.append(f"  - {name}: 掌握度 {degree}/5")

    # 最薄弱知识点
    weak_points = sorted(nodes, key=lambda x: x.get("kg_degree", 5))[:5]
    lines.append(f"\n⚠ 最薄弱的 5 个知识点：")
    for item in weak_points:
        lines.append(f"  - {item.get('kg_node_name', '未知')}: 掌握度 {item.get('kg_degree', 0)}/5")

    return make_tool_result("query_knowledge_mastery", True, {"nodes": make_json_safe(nodes)},
                            "\n".join(lines))


def _build_wrong_exercises_result(stu_id: int) -> dict[str, Any]:
    """构建错题记录的 Agent 工具结果"""
    try:
        exercises = query_wrong_exercises(stu_id, limit=30)
    except Exception as e:
        return make_tool_result("query_wrong_exercises", False, {"exercises": []},
                                f"查询错题记录时数据库连接异常: {str(e)}", "db_error")
    if not exercises:
        return make_tool_result("query_wrong_exercises", False, {"exercises": []},
                                f"学生 {stu_id} 暂无错题记录。该学生可能尚未完成任何练习题，或所有练习均已正确完成。",
                                "no_data")

    lines = [f"学生 {stu_id} 的错题记录（最近 {len(exercises)} 条）："]
    for i, item in enumerate(exercises[:15], 1):
        desc = (item.get("question_description") or "无描述")[:80]
        node = item.get("kg_node_name") or "未绑定知识点"
        score = item.get("do_score", "N/A")
        diff = item.get("question_difficulty", "未知")
        lines.append(f"  {i}. [{node}] {desc}")
        lines.append(f"     难度: {diff} | 得分: {score}")

    if len(exercises) > 15:
        lines.append(f"  ...（共 {len(exercises)} 条，仅展示前 15 条）")

    return make_tool_result("query_wrong_exercises", True, {"exercises": make_json_safe(exercises)},
                            "\n".join(lines))


def _build_wrong_knowledge_result(stu_id: int) -> dict[str, Any]:
    """构建错题知识点分布的 Agent 工具结果"""
    try:
        summary_rows = query_wrong_knowledge_summary(stu_id)
    except Exception as e:
        return make_tool_result("query_wrong_knowledge_summary", False, {"summary": []},
                                f"查询错题知识点分布时数据库连接异常: {str(e)}", "db_error")
    if not summary_rows:
        return make_tool_result("query_wrong_knowledge_summary", False, {"summary": []},
                                f"学生 {stu_id} 的错题没有关联到具体知识点，或暂无错题记录。", "no_data")

    lines = [f"学生 {stu_id} 的错题知识点分布统计（按错题数降序）："]
    for item in summary_rows:
        name = item.get("kg_node_name") or "未绑定"
        count = item.get("wrong_count", 0)
        avg = item.get("avg_score", "N/A")
        if isinstance(avg, float):
            avg = f"{avg:.2f}"
        lines.append(f"  - {name}: 错题 {count} 道，平均得分 {avg}")

    # 高亮错误最多的知识点
    top = summary_rows[0]
    top_name = top.get("kg_node_name") or "未绑定"
    lines.append(f"\n⚠ 错题最集中的知识点是「{top_name}」，需要重点关注。")

    return make_tool_result("query_wrong_knowledge_summary", True, {"summary": make_json_safe(summary_rows)},
                            "\n".join(lines))


# ── 工具执行调度表 ─────────────────────────────────────────────
_TOOL_EXECUTORS: dict[str, Any] = {
    "query_student_level": _build_level_result,
    "query_knowledge_mastery": _build_mastery_result,
    "query_wrong_exercises": _build_wrong_exercises_result,
    "query_wrong_knowledge_summary": _build_wrong_knowledge_result,
}


def execute_analysis_tool(name: str, stu_id: int) -> dict[str, Any]:
    """执行分析工具并返回结构化结果（ReAct Agent 工具协议）

    Args:
        name: 工具名称
        stu_id: 学生 ID

    Returns:
        统一格式的工具结果字典 {tool, success, error_type, data, summary}
        如果工具名未知，返回错误结果。
    """
    executor = _TOOL_EXECUTORS.get(name)
    if executor is None:
        return make_tool_result(name, False, None,
                                f"未知工具: {name}。可用的工具：{list(_TOOL_EXECUTORS.keys())}",
                                "db_error")
    try:
        return executor(stu_id)
    except Exception as e:
        logger.error(f"工具 {name} 执行异常 (stu_id={stu_id}): {e}")
        return make_tool_result(name, False, None,
                                f"工具 {name} 执行失败: {str(e)}", "db_error")


def get_stu_analysis_tool_definitions() -> list[dict]:
    """返回学生分析工具的 OpenAI function-calling 格式定义

    Agent 将此列表传入 LLM 的 tools 参数，LLM 自主决定调用哪些工具。
    工具不需要 LLM 传参 — stu_id 由 Agent 在调用 execute_analysis_tool 时注入。
    """
    return [
        {
            "type": "function",
            "function": {
                "name": "query_student_level",
                "description": (
                    "查询学生的综合评级（A/B/C/D/E）。"
                    "评级反映学生的整体学习水平：A=优秀、B=良好、C=中等、D=较差、E=很差。"
                    "应在分析开始时调用，了解学生的整体定位。"
                ),
                "parameters": {"type": "object", "properties": {}},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "query_knowledge_mastery",
                "description": (
                    "查询学生在各知识点的掌握度（0-5分）。"
                    "返回所有已评估知识点的掌握度分数，按从低到高排列。"
                    "用于发现学生的薄弱知识点和优势领域。"
                ),
                "parameters": {"type": "object", "properties": {}},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "query_wrong_exercises",
                "description": (
                    "查询学生的错题记录列表。"
                    "返回最近做错的练习题，包含题目描述、关联知识点、难度、得分等信息。"
                    "用于分析学生在实际做题中暴露的问题。"
                ),
                "parameters": {"type": "object", "properties": {}},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "query_wrong_knowledge_summary",
                "description": (
                    "统计学生错题在各知识点上的分布情况。"
                    "返回每个知识点的错题数量与平均得分，按错题数降序排列。"
                    "用于识别学生反复出错的知识领域，确定优先改进方向。"
                ),
                "parameters": {"type": "object", "properties": {}},
            },
        },
    ]
