"""教师建议与评价数据库查询工具 — 从 PostgreSQL 获取学生两个维度的数据

两个维度（教师建议与评价专职 Agent 的评估依据）：
1. 学生当下学科的知识图谱进度（知识点掌握程度、学科掌握程度）
2. 学生的 AI 评级（students.stu_level）

所有查询使用 psycopg2 直连 PostgreSQL（复用 AGE 的数据库配置）。

===== ReAct Agent 工具协议 =====

每个工具返回统一的 JSON 结构，同时服务于两个消费者：
- LLM（通过 summary 字段理解查询结果，进行下一步推理）
- 后处理代码（通过 data 字段提取结构化数据，构建 dimensions_detail）

工具返回格式：
{
    "tool": "工具名称",
    "success": true/false,
    "error_type": "db_error" | "no_data" | null,   # 兜底机制判定依据
    "data": { ... 结构化数据 ... },
    "summary": "人类可读的摘要，供 LLM 推理用"
}

error_type 说明（兜底机制核心）：
- "db_error": 数据库连接/查询异常 → 前端显示用户友好错误
- "no_data": 查询成功但该维度无内容 → 前端提示"可能该学生还没有开展学习哦~"
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


def query_student_knowledge_mastery(stu_id: int, course_id: int) -> list[dict[str, Any]]:
    """查询学生在某学科下的知识点掌握度 (student_knowledge_mastery)

    返回该学生在指定学科下所有知识点的掌握度（kg_degree，0~5 分），
    按掌握度从低到高排列，便于识别薄弱知识点。
    """
    try:
        conn = get_conn()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT kg_node_name, kg_degree, answered_count, correct_count "
                "FROM student_knowledge_mastery "
                "WHERE stu_id = %s AND course_id = %s "
                "ORDER BY kg_degree ASC",
                (stu_id, course_id),
            )
            rows = cur.fetchall()
            return [dict(r) for r in rows]
    except Exception as e:
        logger.error(
            f"查询学生知识点掌握度失败 (stu_id={stu_id}, course_id={course_id}): {e}"
        )
        raise
    finally:
        conn.close()


def query_student_course_mastery(stu_id: int, course_id: int) -> dict[str, Any] | None:
    """查询学生在某学科下的学科掌握度 (student_course_mastery)

    返回该学生在指定学科下的整体掌握度（course_degree，0~5 分）
    与学习进度（course_process，0~1）。
    """
    try:
        conn = get_conn()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT course_degree, course_process "
                "FROM student_course_mastery "
                "WHERE stu_id = %s AND course_id = %s",
                (stu_id, course_id),
            )
            row = cur.fetchone()
            return dict(row) if row else None
    except Exception as e:
        logger.error(
            f"查询学生学科掌握度失败 (stu_id={stu_id}, course_id={course_id}): {e}"
        )
        raise
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════════
# ReAct Agent 工具协议层
# ═══════════════════════════════════════════════════════════════

def _build_level_result(stu_id: int) -> dict[str, Any]:
    """构建学生 AI 评级维度的 Agent 工具结果"""
    try:
        level = query_student_level(stu_id)
    except Exception as e:
        return make_tool_result("query_student_level", False, {"level": None},
                                f"查询学生评级时数据库连接异常: {str(e)}", "db_error")
    if not level:
        return make_tool_result("query_student_level", False, {"level": None},
                                f"学生 {stu_id} 暂无 AI 评级记录。", "no_data")
    desc = LEVEL_DESCRIPTION.get(level.upper(), "未知评级")
    return make_tool_result("query_student_level", True, {"level": level},
                            f"学生 {stu_id} 的当前 AI 评级为 {level}（{desc}）。")


def _build_knowledge_mastery_result(stu_id: int, course_id: int) -> dict[str, Any]:
    """构建学生知识点掌握度维度的 Agent 工具结果"""
    try:
        nodes = query_student_knowledge_mastery(stu_id, course_id)
    except Exception as e:
        return make_tool_result("query_student_knowledge_mastery", False, {"nodes": []},
                                f"查询学生知识点掌握度时数据库连接异常: {str(e)}", "db_error")
    if not nodes:
        return make_tool_result("query_student_knowledge_mastery", False, {"nodes": []},
                                f"学生 {stu_id} 在学科 {course_id} 暂无知识点掌握度记录。可能该学生还没有开展学习哦~",
                                "no_data")

    # 构建供 LLM 阅读的摘要
    lines = [f"学生 {stu_id} 在学科 {course_id} 的知识点掌握度（共 {len(nodes)} 个知识点，按掌握度从低到高排列）："]
    for item in nodes:
        name = item.get("kg_node_name", "未知")
        degree = item.get("kg_degree", 0)
        lines.append(f"  - {name}: 掌握度 {degree}/5")

    # 最薄弱知识点
    weak_points = sorted(nodes, key=lambda x: x.get("kg_degree", 5))[:5]
    lines.append(f"\n⚠ 最薄弱的 5 个知识点：")
    for item in weak_points:
        lines.append(f"  - {item.get('kg_node_name', '未知')}: 掌握度 {item.get('kg_degree', 0)}/5")

    return make_tool_result("query_student_knowledge_mastery", True,
                            {"nodes": make_json_safe(nodes)},
                            "\n".join(lines))


def _build_course_mastery_result(stu_id: int, course_id: int) -> dict[str, Any]:
    """构建学生学科掌握度维度的 Agent 工具结果"""
    try:
        mastery = query_student_course_mastery(stu_id, course_id)
    except Exception as e:
        return make_tool_result("query_student_course_mastery", False,
                                {"course_degree": None, "course_process": None},
                                f"查询学生学科掌握度时数据库连接异常: {str(e)}", "db_error")
    if not mastery:
        return make_tool_result("query_student_course_mastery", False,
                                {"course_degree": None, "course_process": None},
                                f"学生 {stu_id} 在学科 {course_id} 暂无学科掌握度记录。可能该学生还没有开展学习哦~",
                                "no_data")

    degree = mastery.get("course_degree")
    process = mastery.get("course_process")
    lines = [f"学生 {stu_id} 在学科 {course_id} 的学科掌握情况："]
    if degree is not None:
        lines.append(f"  - 学科整体掌握度: {degree}/5")
    if process is not None:
        lines.append(f"  - 学科学习进度: {process * 100:.1f}%")

    return make_tool_result("query_student_course_mastery", True,
                            make_json_safe(mastery),
                            "\n".join(lines))


# ── 工具执行调度表 ─────────────────────────────────────────────
_TOOL_EXECUTORS: dict[str, Any] = {
    "query_student_level": _build_level_result,
    "query_student_knowledge_mastery": _build_knowledge_mastery_result,
    "query_student_course_mastery": _build_course_mastery_result,
}


def execute_stu_evaluation_tool(tool_name: str, arguments: dict) -> dict[str, Any]:
    """执行教师建议与评价 Agent 的工具调用，返回统一 JSON 结果

    Args:
        tool_name: 工具名（query_student_level / query_student_knowledge_mastery / query_student_course_mastery）
        arguments: 工具参数（stu_id / course_id）

    Returns:
        统一 JSON 结构，含 success / error_type / data / summary
    """
    executor = _TOOL_EXECUTORS.get(tool_name)
    if executor is None:
        return make_tool_result(tool_name, False, {},
                                f"未知工具: {tool_name}", "db_error")
    # 只提取该工具签名中声明的参数，忽略 LLM 可能多传的无关参数
    import inspect

    sig = inspect.signature(executor)
    filtered = {k: v for k, v in arguments.items() if k in sig.parameters}
    try:
        return executor(**filtered)
    except TypeError as e:
        return make_tool_result(tool_name, False, {},
                                f"工具参数错误: {str(e)}", "db_error")


def get_stu_evaluation_tool_definitions() -> list[dict[str, Any]]:
    """返回教师建议与评价 Agent 可用的工具定义（OpenAI function calling 格式）

    工具由 Agent 动态发现并自主决定调用顺序，不绑定固定工作流。
    """
    return [
        {
            "type": "function",
            "function": {
                "name": "query_student_level",
                "description": (
                    "查询学生的 AI 综合评级（A/B/C/D/E）。"
                    "评级反映学生的整体学习水平：A=优秀、B=良好、C=中等、D=较差、E=很差。"
                    "这是教师建议与评价的两个评估维度之一。"
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "stu_id": {"type": "integer", "description": "学生 ID"},
                    },
                    "required": ["stu_id"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "query_student_knowledge_mastery",
                "description": (
                    "查询学生在某学科下的各知识点掌握度（0-5分）。"
                    "返回该学科下所有已评估知识点的掌握度分数，按从低到高排列。"
                    "用于发现学生的薄弱知识点和优势领域。"
                    "这是教师建议与评价的两个评估维度之一（知识图谱进度）。"
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "stu_id": {"type": "integer", "description": "学生 ID"},
                        "course_id": {"type": "integer", "description": "学科 ID"},
                    },
                    "required": ["stu_id", "course_id"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "query_student_course_mastery",
                "description": (
                    "查询学生在某学科下的学科整体掌握度与学习进度。"
                    "返回学科整体掌握度（course_degree，0-5分）与学习进度（course_process，0-1）。"
                    "用于了解学生在整个学科层面的掌握情况。"
                    "这是教师建议与评价的两个评估维度之一（知识图谱进度）。"
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "stu_id": {"type": "integer", "description": "学生 ID"},
                        "course_id": {"type": "integer", "description": "学科 ID"},
                    },
                    "required": ["stu_id", "course_id"],
                },
            },
        },
    ]
