"""知识图谱注册表 — 从数据库 kg_graphs 表解析可用图谱

用户要求：所有的知识图谱必须从数据库查询出来，再显示到前端拉取页面。
因此不再依赖 .env 中硬编码的 AGE_GRAPH_NAME（chuma_kg）作为默认图，
而是从 PostgreSQL 的 kg_graphs 表查询真实存在的图谱。
"""

import logging
from typing import Optional

import psycopg2

from app.config import settings

logger = logging.getLogger(__name__)


def _build_dsn() -> str:
    """从 settings 构建 PostgreSQL DSN（与 AGE 同一实例）"""
    return (
        f"host={settings.AGE_HOST} "
        f"port={settings.AGE_PORT} "
        f"dbname={settings.AGE_DB} "
        f"user={settings.AGE_USER} "
        f"password={settings.AGE_PASSWORD}"
    )


def list_graph_names(status: Optional[str] = "completed") -> list[str]:
    """从 kg_graphs 表查询图谱名列表。

    Args:
        status: 过滤状态，None 表示不过滤。默认只返回已构建完成的图谱。

    Returns:
        图谱名列表（按创建时间升序，保证稳定）。
    """
    try:
        conn = psycopg2.connect(_build_dsn())
        conn.set_session(autocommit=True)
        try:
            with conn.cursor() as cur:
                if status:
                    cur.execute(
                        "SELECT graph_name FROM kg_graphs "
                        "WHERE status = %s ORDER BY created_at ASC",
                        (status,),
                    )
                else:
                    cur.execute(
                        "SELECT graph_name FROM kg_graphs ORDER BY created_at ASC"
                    )
                return [row[0] for row in cur.fetchall()]
        finally:
            conn.close()
    except Exception as e:
        logger.warning("Failed to list kg_graphs from database: %s", e)
        return []


def resolve_default_graph() -> Optional[str]:
    """解析默认图谱名。

    优先返回数据库中第一个已完成的图谱；若没有则返回任意图谱；
    数据库查询失败或为空时返回 None（调用方应友好处理，而非回退到已删除的 chuma_kg）。
    """
    names = list_graph_names(status="completed")
    if names:
        return names[0]
    names = list_graph_names(status=None)
    return names[0] if names else None
