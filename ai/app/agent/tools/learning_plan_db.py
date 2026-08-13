"""学习规划数据库查询工具 — 从 PostgreSQL 获取四个维度的数据

四个维度（各占 25% 权重，动态调整）：
1. 学生端 AI 分析内容   (evaluation_analysis 中 publisher_name='AI')
2. 学生自身知识图谱     (student_knowledge_mastery，按学科 kg_id 过滤)
3. 习题情况             (exercise_records + questions，按学科 course_id 过滤：题库题目总数 + 已做题目数 → 各科进度)
4. 老师意见与评估       (evaluation_analysis 中 publisher_name != 'AI')

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
- "db_error": 数据库连接/查询异常（如连接失败、表不存在）→ 前端显示用户友好错误
- "no_data": 查询成功但该维度无内容 → 前端提示"可能用户还没有开展学习哦~"
- null:      查询成功且有数据
"""
import json
import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import psycopg2
import psycopg2.extras

from app.config import settings

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# 数据库连接与底层查询函数（不暴露给 Agent）
# ═══════════════════════════════════════════════════════════════

def _get_conn():
    """创建 PostgreSQL 连接（复用 AGE 配置中的数据库连接信息）"""
    conn = psycopg2.connect(
        host=settings.AGE_HOST,
        port=settings.AGE_PORT,
        dbname=settings.AGE_DB,
        user=settings.AGE_USER,
        password=settings.AGE_PASSWORD,
    )
    conn.set_session(autocommit=True)
    return conn


def _make_json_safe(obj: Any) -> Any:
    """递归转换对象中的非 JSON 可序列化类型为安全类型"""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, dict):
        return {k: _make_json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_make_json_safe(item) for item in obj]
    return obj


def query_subjects() -> list[dict[str, Any]]:
    """查询全部学科（courses 表）"""
    try:
        conn = _get_conn()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT course_id, course_name, kg_id "
                "FROM courses ORDER BY course_id"
            )
            rows = cur.fetchall()
            return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"查询学科列表失败: {e}")
        raise
    finally:
        conn.close()


def query_ai_analysis(stu_id: int) -> dict[str, Any] | None:
    """查询学生端 AI 分析内容（evaluation_analysis 中 publisher_name='AI'）"""
    try:
        conn = _get_conn()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT ea_description, updated_at "
                "FROM evaluation_analysis "
                "WHERE stu_id = %s AND publisher_name = 'AI' "
                "ORDER BY updated_at DESC LIMIT 1",
                (stu_id,),
            )
            row = cur.fetchone()
            return dict(row) if row else None
    except Exception as e:
        logger.error(f"查询 AI 分析失败 (stu_id={stu_id}): {e}")
        raise
    finally:
        conn.close()


def query_teacher_opinion(stu_id: int) -> dict[str, Any] | None:
    """查询老师意见与评估（evaluation_analysis 中 publisher_name != 'AI'）"""
    try:
        conn = _get_conn()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT publisher_name, ea_description, updated_at "
                "FROM evaluation_analysis "
                "WHERE stu_id = %s AND publisher_name != 'AI' "
                "ORDER BY updated_at DESC LIMIT 1",
                (stu_id,),
            )
            row = cur.fetchone()
            return dict(row) if row else None
    except Exception as e:
        logger.error(f"查询老师意见失败 (stu_id={stu_id}): {e}")
        raise
    finally:
        conn.close()


def query_knowledge_mastery(stu_id: int, course_id: int) -> list[dict[str, Any]]:
    """查询学生某学科的知识图谱掌握度（student_knowledge_mastery 按 kg_id 过滤）"""
    try:
        conn = _get_conn()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT skm.kg_node_name, skm.kg_degree
                FROM student_knowledge_mastery skm
                JOIN courses c ON c.kg_id = skm.kg_id
                WHERE skm.stu_id = %s AND c.course_id = %s
                ORDER BY skm.kg_degree ASC
                """,
                (stu_id, course_id),
            )
            rows = cur.fetchall()
            return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"查询知识图谱掌握度失败 (stu_id={stu_id}, course_id={course_id}): {e}")
        raise
    finally:
        conn.close()


def query_exercise_progress(stu_id: int, course_id: int) -> dict[str, Any]:
    """查询学生某学科的做题进度

    只需知道该学科题目总数与已做题目数，即可判断各科进度：
    - total_questions: 该学科题库题目总数（questions 表按 course_id 统计）
    - done_count:      该学生已做的题目数（exercise_records 按 stu_id + course_id 统计）
    - progress_rate:   进度比例 = done_count / total_questions
    """
    try:
        conn = _get_conn()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # 该学科题库题目总数
            cur.execute(
                "SELECT COUNT(*) AS total_questions FROM questions WHERE course_id = %s",
                (course_id,),
            )
            total_row = cur.fetchone()
            total_questions = total_row["total_questions"] if total_row else 0

            # 该学生已做的题目数（按题目去重，避免重复做题重复计数）
            cur.execute(
                "SELECT COUNT(DISTINCT question_id) AS done_count "
                "FROM exercise_records "
                "WHERE stu_id = %s AND course_id = %s",
                (stu_id, course_id),
            )
            done_row = cur.fetchone()
            done_count = done_row["done_count"] if done_row else 0

            progress_rate = round(done_count / total_questions, 4) if total_questions else 0.0
            return {
                "total_questions": total_questions,
                "done_count": done_count,
                "progress_rate": progress_rate,
            }
    except Exception as e:
        logger.error(f"查询做题进度失败 (stu_id={stu_id}, course_id={course_id}): {e}")
        raise
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════════
# ReAct Agent 工具协议层
# ═══════════════════════════════════════════════════════════════

def _build_subjects_result() -> dict[str, Any]:
    """构建学科列表的 Agent 工具结果"""
    try:
        subjects = query_subjects()
    except Exception as e:
        return {
            "tool": "query_subjects",
            "success": False,
            "error_type": "db_error",
            "data": {"subjects": []},
            "summary": f"查询学科列表时数据库连接异常: {str(e)}",
        }
    if not subjects:
        return {
            "tool": "query_subjects",
            "success": False,
            "error_type": "no_data",
            "data": {"subjects": []},
            "summary": "数据库中暂无任何学科（courses 表为空）。",
        }
    lines = [f"系统共 {len(subjects)} 门学科，需要为每门学科分别制定学习规划："]
    for s in subjects:
        lines.append(f"  - course_id={s['course_id']}: {s['course_name']}")
    return {
        "tool": "query_subjects",
        "success": True,
        "error_type": None,
        "data": {"subjects": _make_json_safe(subjects)},
        "summary": "\n".join(lines),
    }


def _build_ai_analysis_result(stu_id: int) -> dict[str, Any]:
    """构建 AI 分析维度的 Agent 工具结果"""
    try:
        row = query_ai_analysis(stu_id)
    except Exception as e:
        return {
            "tool": "query_ai_analysis",
            "success": False,
            "error_type": "db_error",
            "data": {"ai_analysis": None},
            "summary": f"查询 AI 分析时数据库连接异常: {str(e)}",
        }
    if not row or not row.get("ea_description"):
        return {
            "tool": "query_ai_analysis",
            "success": False,
            "error_type": "no_data",
            "data": {"ai_analysis": None},
            "summary": f"学生 {stu_id} 暂无 AI 分析内容。可能用户还没有开展学习哦~",
        }
    return {
        "tool": "query_ai_analysis",
        "success": True,
        "error_type": None,
        "data": {"ai_analysis": row.get("ea_description")},
        "summary": f"学生 {stu_id} 的 AI 分析内容已获取（{len(row.get('ea_description') or '')} 字符）。",
    }


def _build_teacher_opinion_result(stu_id: int) -> dict[str, Any]:
    """构建老师意见维度的 Agent 工具结果"""
    try:
        row = query_teacher_opinion(stu_id)
    except Exception as e:
        return {
            "tool": "query_teacher_opinion",
            "success": False,
            "error_type": "db_error",
            "data": {"teacher_opinion": None},
            "summary": f"查询老师意见时数据库连接异常: {str(e)}",
        }
    if not row or not row.get("ea_description"):
        return {
            "tool": "query_teacher_opinion",
            "success": False,
            "error_type": "no_data",
            "data": {"teacher_opinion": None},
            "summary": f"学生 {stu_id} 暂无老师意见与评估。可能用户还没有开展学习哦~",
        }
    return {
        "tool": "query_teacher_opinion",
        "success": True,
        "error_type": None,
        "data": {
            "teacher_opinion": row.get("ea_description"),
            "publisher_name": row.get("publisher_name"),
        },
        "summary": f"学生 {stu_id} 的老师意见已获取（发布者：{row.get('publisher_name')}）。",
    }


def _build_knowledge_mastery_result(stu_id: int, course_id: int) -> dict[str, Any]:
    """构建知识图谱维度的 Agent 工具结果"""
    try:
        nodes = query_knowledge_mastery(stu_id, course_id)
    except Exception as e:
        return {
            "tool": "query_knowledge_mastery",
            "success": False,
            "error_type": "db_error",
            "data": {"nodes": []},
            "summary": f"查询知识图谱掌握度时数据库连接异常: {str(e)}",
        }
    if not nodes:
        return {
            "tool": "query_knowledge_mastery",
            "success": False,
            "error_type": "no_data",
            "data": {"nodes": []},
            "summary": f"学生 {stu_id} 在学科 {course_id} 暂无知识图谱掌握度记录。可能用户还没有开展学习哦~",
        }
    lines = [f"学生 {stu_id} 在学科 {course_id} 的知识图谱掌握度（共 {len(nodes)} 个知识点，按掌握度从低到高）："]
    for item in nodes:
        lines.append(f"  - {item.get('kg_node_name', '未知')}: 掌握度 {item.get('kg_degree', 0)}/5")
    weak = sorted(nodes, key=lambda x: x.get("kg_degree", 5))[:5]
    lines.append("\n⚠ 最薄弱的 5 个知识点：")
    for item in weak:
        lines.append(f"  - {item.get('kg_node_name', '未知')}: 掌握度 {item.get('kg_degree', 0)}/5")
    return {
        "tool": "query_knowledge_mastery",
        "success": True,
        "error_type": None,
        "data": {"nodes": _make_json_safe(nodes)},
        "summary": "\n".join(lines),
    }


def _build_exercise_result(stu_id: int, course_id: int) -> dict[str, Any]:
    """构建习题情况维度的 Agent 工具结果（做题进度）"""
    try:
        progress = query_exercise_progress(stu_id, course_id)
    except Exception as e:
        return {
            "tool": "query_exercise_progress",
            "success": False,
            "error_type": "db_error",
            "data": {"progress": {}},
            "summary": f"查询习题情况时数据库连接异常: {str(e)}",
        }

    total_questions = progress.get("total_questions") or 0
    done_count = progress.get("done_count") or 0
    if total_questions == 0:
        return {
            "tool": "query_exercise_progress",
            "success": False,
            "error_type": "no_data",
            "data": {"progress": _make_json_safe(progress)},
            "summary": f"学科 {course_id} 题库暂无题目，无法统计做题进度。",
        }
    if done_count == 0:
        return {
            "tool": "query_exercise_progress",
            "success": False,
            "error_type": "no_data",
            "data": {"progress": _make_json_safe(progress)},
            "summary": f"学生 {stu_id} 在学科 {course_id} 尚未开始做题。可能用户还没有开展学习哦~",
        }

    progress_rate = progress.get("progress_rate") or 0.0
    lines = [f"学生 {stu_id} 在学科 {course_id} 的做题进度："]
    lines.append(f"  - 该学科题库共 {total_questions} 题，已做 {done_count} 题")
    lines.append(f"  - 做题进度: {progress_rate * 100:.1f}%")

    return {
        "tool": "query_exercise_progress",
        "success": True,
        "error_type": None,
        "data": {"progress": _make_json_safe(progress)},
        "summary": "\n".join(lines),
    }


# ── 工具执行调度表 ─────────────────────────────────────────────
# 每个执行器签名不同（有的需要 course_id），用统一包装处理。
_TOOL_EXECUTORS: dict[str, Any] = {
    "query_subjects": _build_subjects_result,
    "query_ai_analysis": _build_ai_analysis_result,
    "query_teacher_opinion": _build_teacher_opinion_result,
    "query_knowledge_mastery": _build_knowledge_mastery_result,
    "query_exercise_progress": _build_exercise_result,
}


# ── 工具定义（供 Agent 注入到 LLM 的 function calling schema）──
def get_learning_plan_tool_definitions() -> list[dict[str, Any]]:
    """返回学习规划 Agent 可用的工具定义（OpenAI function calling 格式）"""
    return [
        {
            "type": "function",
            "function": {
                "name": "query_subjects",
                "description": "查询系统全部学科（courses 表）。学习规划必须为每门学科分别制定，先调用本工具获取学科列表。",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "query_ai_analysis",
                "description": "查询学生端 AI 分析内容（evaluation_analysis 中 publisher_name='AI'）。这是学习规划四维度之一。",
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
                "name": "query_teacher_opinion",
                "description": "查询老师意见与评估（evaluation_analysis 中 publisher_name != 'AI'）。这是学习规划四维度之一。",
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
                "name": "query_knowledge_mastery",
                "description": "查询学生某学科的知识图谱掌握度（student_knowledge_mastery 按学科 kg_id 过滤）。这是学习规划四维度之一。",
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
                "name": "query_exercise_progress",
                "description": "查询学生某学科的做题进度（该学科题库题目总数 + 学生已做题目数，用于判断各科进度）。这是学习规划四维度之一。",
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


# ── 统一执行入口（供 Agent 调用）───────────────────────────────
def execute_learning_plan_tool(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """执行学习规划工具并返回统一结果结构

    Args:
        tool_name: 工具名称
        arguments: 工具参数（含 stu_id / course_id）

    Returns:
        统一 JSON 结构（含 success / error_type / data / summary）
    """
    executor = _TOOL_EXECUTORS.get(tool_name)
    if executor is None:
        return {
            "tool": tool_name,
            "success": False,
            "error_type": "db_error",
            "data": {},
            "summary": f"未知工具: {tool_name}",
        }

    try:
        if tool_name == "query_subjects":
            return executor()
        if tool_name in ("query_ai_analysis", "query_teacher_opinion"):
            return executor(arguments.get("stu_id"))
        if tool_name in ("query_knowledge_mastery", "query_exercise_progress"):
            return executor(
                arguments.get("stu_id"),
                arguments.get("course_id"),
            )
        return executor()
    except Exception as e:
        logger.error(f"执行工具 {tool_name} 异常: {e}", exc_info=True)
        return {
            "tool": tool_name,
            "success": False,
            "error_type": "db_error",
            "data": {},
            "summary": f"执行工具 {tool_name} 时发生异常: {str(e)}",
        }