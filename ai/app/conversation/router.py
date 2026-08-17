"""AI 助学对话记忆路由 — 历史对话的增删改查接口

所有接口均要求 stu_id 与当前登录学生严格对应：
- 列表：仅返回该学生的对话
- 详情/更新/删除：仅允许操作属于该学生的对话，否则返回 404
"""
import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.conversation import service

logger = logging.getLogger(__name__)

router = APIRouter()


class ConversationCreateRequest(BaseModel):
    """创建对话请求"""
    stu_id: int
    first_message: str = Field(..., min_length=1, description="首次对话内容，用于 AI 生成标题")
    messages: list[dict] = Field(default_factory=list, description="对话历史内容（JSON 数组）")


class ConversationUpdateRequest(BaseModel):
    """更新对话请求"""
    stu_id: int
    messages: list[dict] = Field(default_factory=list, description="对话历史内容（JSON 数组）")


@router.post("/conversations")
async def create_conversation(req: ConversationCreateRequest):
    """创建一条对话记录

    - 标题由 AI 自行总结首次对话内容生成
    - 空对话（messages 为空且无首次消息）不允许存储
    """
    if not req.messages and not req.first_message.strip():
        raise HTTPException(status_code=400, detail="空对话不允许存储")
    title = await service.generate_title(req.first_message)
    conversation_id = service.create_conversation(req.stu_id, title, req.messages)
    return {"conversation_id": conversation_id, "title": title}


@router.get("/conversations")
async def list_conversations(stu_id: int):
    """列出某学生的全部对话（按更新时间倒序）"""
    return service.list_conversations(stu_id)


@router.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: int, stu_id: int):
    """获取某学生的单条对话详情（含完整 messages）"""
    conversation = service.get_conversation(conversation_id, stu_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="对话不存在或无权访问")
    return conversation


@router.put("/conversations/{conversation_id}")
async def update_conversation(conversation_id: int, req: ConversationUpdateRequest):
    """更新对话内容（仅允许更新属于该学生的对话）"""
    if not req.messages:
        raise HTTPException(status_code=400, detail="空对话不允许存储")
    ok = service.update_conversation(conversation_id, req.stu_id, req.messages)
    if not ok:
        raise HTTPException(status_code=404, detail="对话不存在或无权访问")
    return {"success": True}


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: int, stu_id: int):
    """删除某学生的对话（仅允许删除属于该学生的对话）"""
    ok = service.delete_conversation(conversation_id, stu_id)
    if not ok:
        raise HTTPException(status_code=404, detail="对话不存在或无权访问")
    return {"success": True}
