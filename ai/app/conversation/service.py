"""AI 助学对话记忆服务 — 历史对话的增删改查与标题生成

对话记忆功能：
- 以 JSONB 格式存储每次对话的完整历史内容（messages 字段）
- 标题由 AI 自行总结首次对话内容生成，便于用户定位目标对话
- 空对话（无任何消息）不允许存储
- 与当前登录学生严格对应（stu_id），登录用户只能遍历到自己的历史对话

所有查询使用 psycopg2 直连 PostgreSQL（复用 AGE 的数据库配置）。
"""
import json
import logging
from typing import Any

import psycopg2.extras

from app.agent.tools._base import get_conn
from app.engines.llm.client import LLMClient
from app.engines.llm.profiles import remote_profile

logger = logging.getLogger(__name__)

# 标题最大长度（与表字段 VARCHAR(128) 对齐）
TITLE_MAX_LEN = 128


async def generate_title(first_message: str) -> str:
    """使用 AI 总结首次对话内容生成简短标题

    若 AI 调用失败或返回异常，则回退为截断的首条消息文本。
    """
    try:
        llm = LLMClient(default_profile=remote_profile())
        messages = [
            {
                "role": "system",
                "content": (
                    "你是一个对话标题生成助手。请根据用户的第一条提问，"
                    "用不超过 20 个字概括这段对话的主题，直接输出标题本身，"
                    "不要加引号、标点或任何解释。"
                ),
            },
            {"role": "user", "content": first_message},
        ]
        result = await llm.chat(messages, temperature=0.3)
        title = (result.content or "").strip().strip('"').strip("'")
        if title:
            return title[:TITLE_MAX_LEN]
    except Exception as e:
        logger.warning(f"AI 生成对话标题失败，回退为消息截断: {e}")
    # 回退：取首条消息前若干字符作为标题
    fallback = first_message.strip().replace("\n", " ")
    return fallback[:TITLE_MAX_LEN] if fallback else "未命名对话"


def create_conversation(stu_id: int, title: str, messages: list[dict]) -> int:
    """创建一条对话记录，返回 conversation_id

    Args:
        stu_id: 登录学生 ID（严格对应）
        title: 对话标题（AI 总结生成）
        messages: 对话历史内容（JSON 数组）
    """
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO chat_conversations (stu_id, title, messages) "
                "VALUES (%s, %s, %s) RETURNING conversation_id",
                (stu_id, title, json.dumps(messages, ensure_ascii=False)),
            )
            row = cur.fetchone()
            return int(row[0])
    finally:
        conn.close()


def update_conversation(conversation_id: int, stu_id: int, messages: list[dict]) -> bool:
    """更新对话内容（仅允许更新属于该学生的对话）

    Returns:
        True 表示更新成功；False 表示对话不存在或不属于该学生。
    """
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE chat_conversations "
                "SET messages = %s, updated_at = now() "
                "WHERE conversation_id = %s AND stu_id = %s",
                (json.dumps(messages, ensure_ascii=False), conversation_id, stu_id),
            )
            return cur.rowcount > 0
    finally:
        conn.close()


def list_conversations(stu_id: int) -> list[dict[str, Any]]:
    """列出某学生的全部对话（按更新时间倒序），仅返回列表所需字段"""
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT conversation_id, title, created_at, updated_at "
                "FROM chat_conversations "
                "WHERE stu_id = %s "
                "ORDER BY updated_at DESC",
                (stu_id,),
            )
            rows = cur.fetchall()
            return [dict(r) for r in rows]
    finally:
        conn.close()


def get_conversation(conversation_id: int, stu_id: int) -> dict[str, Any] | None:
    """获取某学生的单条对话详情（含完整 messages）

    仅返回属于该学生的对话；否则返回 None。
    """
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT conversation_id, stu_id, title, messages, created_at, updated_at "
                "FROM chat_conversations "
                "WHERE conversation_id = %s AND stu_id = %s",
                (conversation_id, stu_id),
            )
            row = cur.fetchone()
            if row is None:
                return None
            result = dict(row)
            # messages 为 JSONB，psycopg2 返回 str，需解析为列表
            if isinstance(result.get("messages"), str):
                result["messages"] = json.loads(result["messages"])
            return result
    finally:
        conn.close()


def delete_conversation(conversation_id: int, stu_id: int) -> bool:
    """删除某学生的对话（仅允许删除属于该学生的对话）

    Returns:
        True 表示删除成功；False 表示对话不存在或不属于该学生。
    """
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM chat_conversations "
                "WHERE conversation_id = %s AND stu_id = %s",
                (conversation_id, stu_id),
            )
            return cur.rowcount > 0
    finally:
        conn.close()
