"""班级教学建议数据库查询工具 — 从 PostgreSQL 获取三个维度的班级数据

三个维度（各占 1/3 权重，动态调整）：
1. 学生评级分布   (students.stu_level，按班级聚合)
2. 班级知识点平均掌握度进度 (student_knowledge_mastery / student_course_mastery，按班级聚合)
3. 疑难章节与知识点 (exercise_records 错题，按班级聚合；疑难章节与知识点视为同一维度)

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
- "no_data": 查询成功但该维度无内容 → 前端提示"可能该班级还没有开展学习哦~"
- null:      查询成功且有数据
"""
import logging
from typing import Any

import psycopg2
import psycopg2.extras

from app.agent.tools._base import get_conn, make_json_safe, make_tool_result

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# 数据库连接与底层查询函数（不暴露给 Agent）
# ═══════════════════════════════════════════════════════════════


def query_class_students(class_id: int) -> list[dict[str, Any]]:
    """查询班级内所有学生的评级分布（students.stu_level）"""
    try:
        conn = get_conn()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT stu_id, stu_name, stu_level "
                "FROM students "
                "WHERE class_id = %s "
                "ORDER BY stu_id",
                (class_id,),
            )
            rows = cur.fetchall()
            return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"查询班级学生评级失败 (class_id={class_id}): {e}")
        raise
    finally:
        conn.close()


def query_class_mastery(class_id: int, course_id: int) -> dict[str, Any]:
    """查询班级在某学科下的知识点平均掌握度与整体进度

    聚合逻辑：
    - 平均掌握度：student_knowledge_mastery 中该班级所有学生在某学科下
      所有知识点 kg_degree 的平均值（0~5 分）
    - 整体进度：student_course_mastery 中该班级所有学生在某学科下
      course_process 的平均值（0~1）
    - 薄弱知识点：按知识点名聚合，取平均掌握度最低的前若干项
    """
    try:
        conn = get_conn()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # 班级学生 ID 集合
            cur.execute(
                "SELECT stu_id FROM students WHERE class_id = %s",
                (class_id,),
            )
            stu_ids = [r["stu_id"] for r in cur.fetchall()]
            if not stu_ids:
                return {"avg_degree": None, "avg_process": None, "node_count": 0, "weakest_nodes": []}

            # 知识点平均掌握度（按知识点聚合）
            cur.execute(
                """
                SELECT kg_node_name,
                       AVG(kg_degree) AS avg_degree,
                       COUNT(*) AS student_count
                FROM student_knowledge_mastery
                WHERE course_id = %s AND stu_id = ANY(%s)
                GROUP BY kg_node_name
                ORDER BY avg_degree ASC
                """,
                (course_id, list(stu_ids)),
            )
            node_rows = cur.fetchall()

            # 学科整体进度（student_course_mastery 平均）
            cur.execute(
                """
                SELECT AVG(course_process) AS avg_process,
                       AVG(course_degree) AS avg_course_degree
                FROM student_course_mastery
                WHERE course_id = %s AND stu_id = ANY(%s)
                """,
                (course_id, list(stu_ids)),
            )
            process_row = cur.fetchone()

            nodes = [dict(r) for r in node_rows]
            avg_degree = (
                round(sum(n["avg_degree"] for n in nodes) / len(nodes), 4)
                if nodes else None
            )
            weakest_nodes = [
                {
                    "name": n.get("kg_node_name", "未知"),
                    "avg_degree": round(n.get("avg_degree") or 0, 4),
                    "student_count": n.get("student_count") or 0,
                }
                for n in nodes[:5]
            ]

            return {
                "avg_degree": avg_degree,
                "avg_process": round(process_row["avg_process"], 4) if process_row and process_row["avg_process"] is not None else None,
                "avg_course_degree": round(process_row["avg_course_degree"], 4) if process_row and process_row["avg_course_degree"] is not None else None,
                "node_count": len(nodes),
                "weakest_nodes": weakest_nodes,
            }
    except Exception as e:
        logger.error(f"查询班级掌握度失败 (class_id={class_id}, course_id={course_id}): {e}")
        raise
    finally:
        conn.close()


def query_class_difficult(class_id: int, course_id: int) -> dict[str, Any]:
    """查询班级在某学科下的疑难章节与知识点（错题聚合）

    疑难章节与知识点视为同一维度：
    - difficult_chapters: 错题知识点归类到顶层章节后的分布（复用教师端疑难章节逻辑）
    - difficult_knowledge: 错题知识点分布（复用教师端疑难知识点词云逻辑）
    """
    try:
        conn = get_conn()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # 错题知识点分布（按知识点聚合）
            cur.execute(
                """
                SELECT COALESCE(NULLIF(TRIM(er.kg_node_name), ''), NULLIF(TRIM(q.kg_node_name), '')) AS knowledge_name,
                       COUNT(er.do_id) AS wrong_count
                FROM exercise_records er
                JOIN students s ON s.stu_id = er.stu_id
                JOIN questions q ON q.question_id = er.question_id
                WHERE s.class_id = %s
                  AND er.course_id = %s
                  AND er.do_istrue = FALSE
                  AND COALESCE(NULLIF(TRIM(er.kg_node_name), ''), NULLIF(TRIM(q.kg_node_name), '')) IS NOT NULL
                GROUP BY COALESCE(NULLIF(TRIM(er.kg_node_name), ''), NULLIF(TRIM(q.kg_node_name), ''))
                ORDER BY wrong_count DESC
                """,
                (class_id, course_id),
            )
            knowledge_rows = cur.fetchall()

            # 错题总数
            cur.execute(
                """
                SELECT COUNT(er.do_id) AS total_wrong
                FROM exercise_records er
                JOIN students s ON s.stu_id = er.stu_id
                WHERE s.class_id = %s AND er.course_id = %s AND er.do_istrue = FALSE
                """,
                (class_id, course_id),
            )
            total_row = cur.fetchone()
            total_wrong = total_row["total_wrong"] if total_row else 0

            knowledge_items = [
                {
                    "name": r.get("knowledge_name") or "未知",
                    "wrong_count": r.get("wrong_count") or 0,
                    "ratio": round((r.get("wrong_count") or 0) / total_wrong, 4) if total_wrong else 0.0,
                }
                for r in knowledge_rows
            ]

            return {
                "total_wrong": total_wrong,
                "difficult_knowledge": knowledge_items[:20],
                "difficult_chapters": [],  # 章节归类依赖知识图谱结构，由 Agent 侧补充或留空
            }
    except Exception as e:
        logger.error(f"查询班级疑难知识点失败 (class_id={class_id}, course_id={course_id}): {e}")
        raise
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════════
# ReAct Agent 工具协议层
# ═══════════════════════════════════════════════════════════════

def _build_students_result(class_id: int) -> dict[str, Any]:
    """构建学生评级维度的 Agent 工具结果"""
    try:
        students = query_class_students(class_id)
    except Exception as e:
        return make_tool_result("query_class_students", False,
                                {"students": [], "level_distribution": {}},
                                f"查询班级学生评级时数据库连接异常: {str(e)}", "db_error")
    if not students:
        return make_tool_result("query_class_students", False,
                                {"students": [], "level_distribution": {}},
                                f"班级 {class_id} 暂无学生数据。可能该班级还没有学生哦~", "no_data")

    # 统计评级分布
    distribution: dict[str, int] = {}
    for s in students:
        level = (s.get("stu_level") or "未知").upper()
        distribution[level] = distribution.get(level, 0) + 1

    lines = [f"班级 {class_id} 共 {len(students)} 名学生，评级分布如下："]
    for level in sorted(distribution.keys()):
        lines.append(f"  - {level}: {distribution[level]} 人")
    lines.append("\n⚠ 评级越低（D/E）的学生越多，说明班级整体基础越薄弱，需要重点关注。")

    return make_tool_result("query_class_students", True,
                            {"students": make_json_safe(students), "level_distribution": distribution},
                            "\n".join(lines))


def _build_mastery_result(class_id: int, course_id: int) -> dict[str, Any]:
    """构建班级掌握度维度的 Agent 工具结果"""
    try:
        mastery = query_class_mastery(class_id, course_id)
    except Exception as e:
        return make_tool_result("query_class_mastery", False,
                                {"avg_degree": None, "avg_process": None, "node_count": 0, "weakest_nodes": []},
                                f"查询班级掌握度时数据库连接异常: {str(e)}", "db_error")

    if not mastery.get("node_count"):
        return make_tool_result("query_class_mastery", False, mastery,
                                f"班级 {class_id} 在学科 {course_id} 暂无知识点掌握度记录。可能该班级还没有开展学习哦~", "no_data")

    lines = [f"班级 {class_id} 在学科 {course_id} 的知识点掌握情况："]
    lines.append(f"  - 知识点平均掌握度: {mastery['avg_degree']}/5")
    if mastery.get("avg_process") is not None:
        lines.append(f"  - 学科整体进度: {mastery['avg_process'] * 100:.1f}%")
    lines.append(f"  - 已评估知识点数: {mastery['node_count']}")
    lines.append("\n⚠ 平均掌握度最低的 5 个知识点：")
    for n in mastery.get("weakest_nodes", []):
        lines.append(f"  - {n['name']}: 平均掌握度 {n['avg_degree']}/5")

    return make_tool_result("query_class_mastery", True, make_json_safe(mastery),
                            "\n".join(lines))


def _build_difficult_result(class_id: int, course_id: int) -> dict[str, Any]:
    """构建疑难章节与知识点维度的 Agent 工具结果"""
    try:
        difficult = query_class_difficult(class_id, course_id)
    except Exception as e:
        return make_tool_result("query_class_difficult", False,
                                {"total_wrong": 0, "difficult_knowledge": [], "difficult_chapters": []},
                                f"查询班级疑难知识点时数据库连接异常: {str(e)}", "db_error")

    if not difficult.get("total_wrong"):
        return make_tool_result("query_class_difficult", False, difficult,
                                f"班级 {class_id} 在学科 {course_id} 暂无错题记录。可能该班级还没有开展练习哦~", "no_data")

    lines = [f"班级 {class_id} 在学科 {course_id} 的疑难知识点分布（共 {difficult['total_wrong']} 道错题）："]
    for item in difficult.get("difficult_knowledge", [])[:10]:
        lines.append(f"  - {item['name']}: 错题 {item['wrong_count']} 道，占比 {item['ratio'] * 100:.1f}%")

    return make_tool_result("query_class_difficult", True, make_json_safe(difficult),
                            "\n".join(lines))


# ── 工具执行调度表 ─────────────────────────────────────────────
_TOOL_EXECUTORS: dict[str, Any] = {
    "query_class_students": _build_students_result,
    "query_class_mastery": _build_mastery_result,
    "query_class_difficult": _build_difficult_result,
}


# ── 工具定义（供 Agent 注入到 LLM 的 function calling schema）──
def get_class_teaching_tool_definitions() -> list[dict[str, Any]]:
    """返回班级教学建议 Agent 可用的工具定义（OpenAI function calling 格式）"""
    return [
        {
            "type": "function",
            "function": {
                "name": "query_class_students",
                "description": "查询班级内所有学生的评级分布（students.stu_level，A/B/C/D/E）。这是班级教学建议三维度之一。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "class_id": {"type": "integer", "description": "班级 ID"},
                    },
                    "required": ["class_id"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "query_class_mastery",
                "description": "查询班级在某学科下的知识点平均掌握度与整体进度（student_knowledge_mastery / student_course_mastery 聚合）。这是班级教学建议三维度之一。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "class_id": {"type": "integer", "description": "班级 ID"},
                        "course_id": {"type": "integer", "description": "学科 ID"},
                    },
                    "required": ["class_id", "course_id"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "query_class_difficult",
                "description": "查询班级在某学科下的疑难章节与知识点分布（exercise_records 错题聚合）。疑难章节与知识点视为同一维度。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "class_id": {"type": "integer", "description": "班级 ID"},
                        "course_id": {"type": "integer", "description": "学科 ID"},
                    },
                    "required": ["class_id", "course_id"],
                },
            },
        },
    ]


def execute_class_teaching_tool(tool_name: str, arguments: dict) -> dict[str, Any]:
    """执行班级教学建议 Agent 的工具调用，返回统一 JSON 结果

    Args:
        tool_name: 工具名（query_class_students / query_class_mastery / query_class_difficult）
        arguments: 工具参数（class_id / course_id）

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