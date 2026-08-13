"""互动消息 Pydantic 请求/响应模型"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class InteractionMessageCreate(BaseModel):
    """发布互动消息请求"""
    msg_texts: str


class InteractionMessageResponse(BaseModel):
    """互动消息响应（含发布者姓名）"""
    msg_id: int
    msg_texts: str
    stu_id: int
    stu_name: Optional[str] = None
    answer_num: int
    created_at: datetime
    class Config:
        from_attributes = True


class InteractionMessageListResponse(BaseModel):
    """互动消息分页列表响应"""
    total: int
    items: list[InteractionMessageResponse]


class InteractionAnswerCreate(BaseModel):
    """发布回答请求"""
    msg_id: int
    answer_text: str


class InteractionAnswerResponse(BaseModel):
    """互动回答响应（含回答者姓名与身份）"""
    answer_id: int
    answer_text: str
    msg_id: int
    stu_id: Optional[int] = None
    tea_id: Optional[int] = None
    author_name: Optional[str] = None
    author_type: Optional[str] = None  # student / teacher
    created_at: datetime
    class Config:
        from_attributes = True
