"""互动消息路由"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.deps import get_current_user_optional
from app.schemas.interaction import (
    InteractionMessageCreate,
    InteractionMessageResponse,
    InteractionMessageListResponse,
    InteractionAnswerCreate,
    InteractionAnswerResponse,
)
from app.services.interaction_service import InteractionService

router = APIRouter()


@router.post("/messages", response_model=InteractionMessageResponse)
async def create_message(
    data: InteractionMessageCreate,
    current_user: dict = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    """学生发布一条互动消息"""
    stu_id = current_user.get("id")
    service = InteractionService()
    try:
        return await service.create_message(stu_id, data, db)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/messages", response_model=InteractionMessageListResponse)
async def list_messages(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """分页查询互动消息列表（按时间倒序）"""
    service = InteractionService()
    return await service.list_messages(db, page, page_size)


@router.get("/messages/{msg_id}", response_model=InteractionMessageResponse)
async def get_message_detail(msg_id: int, db: AsyncSession = Depends(get_db)):
    """查询单条互动消息详情"""
    service = InteractionService()
    result = await service.get_message_detail(msg_id, db)
    if result is None:
        raise HTTPException(status_code=404, detail="互动消息不存在")
    return result


@router.post("/answers", response_model=InteractionAnswerResponse)
async def create_answer(
    data: InteractionAnswerCreate,
    current_user: dict = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    """发布一条回答（学生或老师）"""
    user_type = current_user.get("user_type")
    user_id = current_user.get("id")
    stu_id = user_id if user_type == "student" else None
    tea_id = user_id if user_type == "teacher" else None
    service = InteractionService()
    try:
        return await service.create_answer(data.msg_id, data.answer_text, stu_id, tea_id, db)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/messages/{msg_id}/answers", response_model=list[InteractionAnswerResponse])
async def list_answers(msg_id: int, db: AsyncSession = Depends(get_db)):
    """查询某条消息下的所有回答"""
    service = InteractionService()
    return await service.list_answers(msg_id, db)
