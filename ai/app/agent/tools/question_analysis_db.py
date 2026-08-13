"""AI 题目分析与解惑 — 数据库与知识图谱查询工具

针对每一道题目，AI 分析与解惑从两个维度展开：
1. **题目与答案深度剖析**：从题目题干和所有选项本身出发，深度剖析，
   拆解错误答案对正确答案造成的知识误区（为什么错、错在哪、如何纠正）。
2. **GraphRAG + 知识图谱局部网络视角**：结合知识图谱，形成该题目涉及的
   局部知识点网络视角，精准抽象出题目背后的知识点，再结合该学科知识图谱
   的 1 跳节点邻居进行遍历与分析。

本模块负责从 PostgreSQL（题目、学科、图谱元数据）与 Apache AGE（图节点、
1 跳邻居）中查询所需数据，供上层 Agent 组装分析。

===== 数据来源 =====
- questions 表：题目题干、选项、答案、解析、类型、难度、所属学科、知识点名
- courses 表：学科 → kg_id 映射
- kg_graphs 表：kg_id → graph_name（AGE 图名）
- Apache AGE：按 graph_name 查询图，按知识点名定位中心节点，取 1 跳邻居
"""
import json
import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import psycopg2
import psycopg2.extras

from app.config import settings
from app.kg_pipeline.queries import GraphQueryError, search_nodes
from app.kg_pipeline.storage import AgeStorage

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# 数据库连接与底层查询函数
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


def query_question(question_id: int) -> dict[str, Any] | None:
    """按题目 ID 查询题目完整信息（题干、选项、答案、解析、类型、难度、学科、知识点名）"""
    try:
        conn = _get_conn()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT question_id, course_id, question_description, "
                "question_options, question_answer, question_explanation, "
                "question_type, question_difficulty, kg_node_name "
                "FROM questions WHERE question_id = %s",
                (question_id,),
            )
            row = cur.fetchone()
            return dict(row) if row else None
    except Exception as e:
        logger.error(f"查询题目失败 (question_id={question_id}): {e}")
        raise
    finally:
        conn.close()


def query_course_graph_name(course_id: int) -> str | None:
    """查询学科对应的 AGE 图名（course → kg_id → kg_graphs.graph_name）"""
    try:
        conn = _get_conn()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT c.course_name, g.graph_name "
                "FROM courses c "
                "LEFT JOIN kg_graphs g ON g.id = c.kg_id "
                "WHERE c.course_id = %s",
                (course_id,),
            )
            row = cur.fetchone()
            if not row:
                return None
            return row.get("graph_name")
    except Exception as e:
        logger.error(f"查询学科图谱名失败 (course_id={course_id}): {e}")
        raise
    finally:
        conn.close()


def query_course_name(course_id: int) -> str | None:
    """查询学科名称"""
    try:
        conn = _get_conn()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT course_name FROM courses WHERE course_id = %s",
                (course_id,),
            )
            row = cur.fetchone()
            return row.get("course_name") if row else None
    except Exception as e:
        logger.error(f"查询学科名称失败 (course_id={course_id}): {e}")
        raise
    finally:
        conn.close()


def query_student_answer(stu_id: int, question_id: int) -> str | None:
    """查询某学生对该题最近一次提交的答案（do_stu_answer）

    用于前端未直接传入学生答案时的兜底查询。
    """
    try:
        conn = _get_conn()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT do_stu_answer FROM exercise_records "
                "WHERE stu_id = %s AND question_id = %s "
                "ORDER BY created_at DESC LIMIT 1",
                (stu_id, question_id),
            )
            row = cur.fetchone()
            return row.get("do_stu_answer") if row else None
    except Exception as e:
        logger.error(
            f"查询学生作答失败 (stu_id={stu_id}, question_id={question_id}): {e}"
        )
        raise
    finally:
        conn.close()


def query_center_node(graph_name: str, kg_node_name: str) -> dict[str, Any] | None:
    """在指定图中按知识点名定位中心节点

    优先精确匹配，其次模糊搜索（CONTAINS）。
    """
    try:
        # 先尝试精确匹配
        storage = AgeStorage(graph_name=graph_name)
        conn = storage._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("LOAD 'age';")
                cur.execute("SET search_path TO ag_catalog, public;")
                cur.execute(
                    f"SELECT * FROM cypher('{storage._graph_name}', $$ "
                    f"MATCH (n:Entity) "
                    f"WHERE n.name = '{_escape(kg_node_name)}' "
                    f"RETURN n.id, n.name, n.type, n.description LIMIT 1 "
                    f"$$) AS (id agtype, name agtype, type agtype, description agtype)"
                )
                row = cur.fetchone()
                if row:
                    return {
                        "id": _strip_agtype(row[0]),
                        "name": _strip_agtype(row[1]),
                        "type": _strip_agtype(row[2]),
                        "description": _strip_agtype(row[3]),
                    }
        finally:
            conn.close()
    except Exception as e:
        logger.warning(f"精确匹配中心节点失败 (graph={graph_name}, node={kg_node_name}): {e}")

    # 精确匹配失败 → 模糊搜索
    try:
        results = search_nodes(kg_node_name, graph_name=graph_name)
        if results:
            return results[0]
    except GraphQueryError as e:
        logger.warning(f"模糊搜索中心节点失败 (graph={graph_name}, node={kg_node_name}): {e}")

    return None


def query_one_hop_neighbors(graph_name: str, center_id: str) -> list[dict[str, Any]]:
    """查询中心节点的 1 跳邻居（出边 + 入边），形成局部知识点网络

    返回每条邻居关系：邻居节点信息 + 关系信息 + 方向。
    """
    storage = AgeStorage(graph_name=graph_name)
    try:
        conn = storage._get_conn()
    except Exception as e:
        logger.error(f"连接 AGE 失败 (graph={graph_name}): {e}")
        raise
    try:
        with conn.cursor() as cur:
            cur.execute("LOAD 'age';")
            cur.execute("SET search_path TO ag_catalog, public;")

            # 出边：center -> neighbor
            cur.execute(
                f"SELECT * FROM cypher('{storage._graph_name}', $$ "
                f"MATCH (a:Entity {{id: '{_escape(center_id)}'}})-[r:RELATION]->(b:Entity) "
                f"RETURN b.id, b.name, b.type, b.description, "
                f"r.relationship_name, r.description, 'out' AS direction "
                f"$$) AS (id agtype, name agtype, type agtype, description agtype, "
                f"rel agtype, rel_desc agtype, direction agtype)"
            )
            out_rows = cur.fetchall()

            # 入边：neighbor -> center
            cur.execute(
                f"SELECT * FROM cypher('{storage._graph_name}', $$ "
                f"MATCH (a:Entity)-[r:RELATION]->(b:Entity {{id: '{_escape(center_id)}'}}) "
                f"RETURN a.id, a.name, a.type, a.description, "
                f"r.relationship_name, r.description, 'in' AS direction "
                f"$$) AS (id agtype, name agtype, type agtype, description agtype, "
                f"rel agtype, rel_desc agtype, direction agtype)"
            )
            in_rows = cur.fetchall()
    except Exception as e:
        logger.error(f"查询 1 跳邻居失败 (graph={graph_name}, center={center_id}): {e}")
        raise
    finally:
        conn.close()

    neighbors: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for row in list(out_rows) + list(in_rows):
        nid = _strip_agtype(row[0])
        rel = _strip_agtype(row[4])
        direction = _strip_agtype(row[6])
        key = (nid, rel, direction)
        if key in seen:
            continue
        seen.add(key)
        neighbors.append({
            "node_id": nid,
            "node_name": _strip_agtype(row[1]),
            "node_type": _strip_agtype(row[2]),
            "node_description": _strip_agtype(row[3]),
            "relationship_name": rel,
            "relationship_description": _strip_agtype(row[5]),
            "direction": direction,
        })
    return neighbors


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")


def _strip_agtype(value) -> str:
    """去掉 AGE agtype 返回值的外层引号"""
    if value is None:
        return ""
    s = str(value)
    if s.startswith('"') and s.endswith('"'):
        s = s[1:-1]
    return s


# ═══════════════════════════════════════════════════════════════
# 统一工具结果协议层（与 learning_plan_db 保持一致）
# ═══════════════════════════════════════════════════════════════

def _build_question_result(question_id: int) -> dict[str, Any]:
    """构建题目查询结果"""
    try:
        question = query_question(question_id)
    except Exception as e:
        return {
            "tool": "query_question",
            "success": False,
            "error_type": "db_error",
            "data": {"question": None},
            "summary": f"查询题目时数据库连接异常: {str(e)}",
        }
    if not question:
        return {
            "tool": "query_question",
            "success": False,
            "error_type": "no_data",
            "data": {"question": None},
            "summary": f"题目 {question_id} 不存在。",
        }
    return {
        "tool": "query_question",
        "success": True,
        "error_type": None,
        "data": {"question": _make_json_safe(question)},
        "summary": f"题目 {question_id} 已获取（{question.get('question_type', '未知类型')}）。",
    }


def _build_graph_context_result(
    course_id: int,
    kg_node_name: str,
) -> dict[str, Any]:
    """构建知识图谱局部网络视角结果（中心节点 + 1 跳邻居）"""
    try:
        graph_name = query_course_graph_name(course_id)
    except Exception as e:
        return {
            "tool": "query_graph_context",
            "success": False,
            "error_type": "db_error",
            "data": {"graph_context": None},
            "summary": f"查询学科图谱时数据库连接异常: {str(e)}",
        }

    if not graph_name:
        return {
            "tool": "query_graph_context",
            "success": False,
            "error_type": "no_data",
            "data": {"graph_context": None},
            "summary": f"学科 {course_id} 未关联知识图谱，无法进行图谱视角分析。",
        }

    # 定位中心节点
    try:
        center = query_center_node(graph_name, kg_node_name)
    except Exception as e:
        return {
            "tool": "query_graph_context",
            "success": False,
            "error_type": "db_error",
            "data": {"graph_context": None},
            "summary": f"定位中心节点时数据库连接异常: {str(e)}",
        }

    if not center:
        return {
            "tool": "query_graph_context",
            "success": False,
            "error_type": "no_data",
            "data": {"graph_context": None},
            "summary": f"知识图谱中未找到知识点「{kg_node_name}」，无法进行图谱视角分析。",
        }

    # 查询 1 跳邻居
    try:
        neighbors = query_one_hop_neighbors(graph_name, center["id"])
    except Exception as e:
        return {
            "tool": "query_graph_context",
            "success": False,
            "error_type": "db_error",
            "data": {"graph_context": None},
            "summary": f"查询 1 跳邻居时数据库连接异常: {str(e)}",
        }

    context = {
        "graph_name": graph_name,
        "center_node": center,
        "neighbors": _make_json_safe(neighbors),
        "neighbor_count": len(neighbors),
    }

    lines = [f"学科 {course_id} 的知识图谱局部网络视角（图：{graph_name}）："]
    lines.append(f"  中心知识点：{center.get('name', kg_node_name)}（类型：{center.get('type', 'Concept')}）")
    if center.get("description"):
        lines.append(f"  中心知识点描述：{center['description']}")
    if neighbors:
        lines.append(f"  1 跳邻居共 {len(neighbors)} 个：")
        for nb in neighbors:
            arrow = "→" if nb["direction"] == "out" else "←"
            lines.append(
                f"    {nb['node_name']} {arrow} 关系「{nb['relationship_name']}」"
            )
    else:
        lines.append("  该中心知识点暂无 1 跳邻居。")

    return {
        "tool": "query_graph_context",
        "success": True,
        "error_type": None,
        "data": {"graph_context": context},
        "summary": "\n".join(lines),
    }


# ── 工具执行调度表 ─────────────────────────────────────────────
_TOOL_EXECUTORS: dict[str, Any] = {
    "query_question": _build_question_result,
    "query_graph_context": _build_graph_context_result,
}


# ── 工具定义（供 Agent 注入到 LLM 的 function calling schema）──
def get_question_analysis_tool_definitions() -> list[dict[str, Any]]:
    """返回 AI 题目分析 Agent 可用的工具定义（OpenAI function calling 格式）"""
    return [
        {
            "type": "function",
            "function": {
                "name": "query_question",
                "description": "查询题目完整信息（题干、所有选项、正确答案、解析、类型、难度、所属学科、知识点名）。AI 题目分析的第一步，必须先调用本工具获取题目数据。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "question_id": {"type": "integer", "description": "题目 ID"},
                    },
                    "required": ["question_id"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "query_graph_context",
                "description": "查询题目所属学科的知识图谱局部网络视角：定位题目背后的中心知识点，并遍历其 1 跳节点邻居，形成局部知识点网络。用于 GraphRAG 视角的深度分析。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "course_id": {"type": "integer", "description": "学科 ID"},
                        "kg_node_name": {"type": "string", "description": "题目对应的知识点名称"},
                    },
                    "required": ["course_id", "kg_node_name"],
                },
            },
        },
    ]


# ── 统一执行入口（供 Agent 调用）───────────────────────────────
def execute_question_analysis_tool(
    tool_name: str,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    """执行 AI 题目分析工具并返回统一结果结构

    Args:
        tool_name: 工具名称
        arguments: 工具参数（含 question_id / course_id / kg_node_name）

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
        if tool_name == "query_question":
            return executor(arguments.get("question_id"))
        if tool_name == "query_graph_context":
            return executor(
                arguments.get("course_id"),
                arguments.get("kg_node_name"),
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