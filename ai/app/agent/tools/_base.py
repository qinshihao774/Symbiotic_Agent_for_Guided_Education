"""Agent 工具公共基础设施 — 数据库连接、类型转换、工具结果构建

本模块集中了所有 Agent 工具文件（*_db.py）共用的基础设施：
- get_conn(): PostgreSQL 连接（复用 AGE 的数据库配置）
- make_json_safe(): 递归转换 psycopg2 返回的非 JSON 可序列化类型
- make_tool_result(): 构建统一的 ReAct Agent 工具协议结果
"""
import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import psycopg2
import psycopg2.extras

from app.config import settings

logger = logging.getLogger(__name__)


def get_conn():
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


def make_json_safe(obj: Any) -> Any:
    """递归转换对象中的非 JSON 可序列化类型为安全类型

    psycopg2 返回的 datetime / date / Decimal 无法被 json.dumps 处理，
    此函数在数据进入工具结果前将其转换。
    """
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, dict):
        return {k: make_json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [make_json_safe(item) for item in obj]
    return obj


def make_tool_result(
    tool_name: str,
    success: bool,
    data: Any,
    summary: str,
    error_type: str | None = None,
) -> dict[str, Any]:
    """构建统一的 ReAct Agent 工具协议结果

    Args:
        tool_name: 工具名称
        success: 是否成功
        data: 结构化数据（供后处理代码使用）
        summary: 人类可读的摘要（供 LLM 推理用）
        error_type: 错误类型（"db_error" / "no_data" / None）
    """
    return {
        "tool": tool_name,
        "success": success,
        "error_type": error_type,
        "data": data,
        "summary": summary,
    }
