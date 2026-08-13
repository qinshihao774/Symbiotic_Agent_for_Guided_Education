"""Practice Pydantic 请求/响应模型"""
from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel


class QuestionCreate(BaseModel):
    question_description: str
    question_answer: str
    question_options: Optional[Any] = None
    question_type: str
    question_difficulty: int
    question_explanation: Optional[str] = None
    course_id: int
    kg_node_name: Optional[str] = None


class QuestionResponse(BaseModel):
    question_id: int
    question_description: str
    question_answer: str
    question_options: Optional[Any] = None
    question_type: str
    question_difficulty: int
    question_explanation: Optional[str] = None
    course_id: int
    kg_node_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    class Config:
        from_attributes = True


class ExerciseRecordCreate(BaseModel):
    question_id: int
    course_id: int
    kg_node_name: Optional[str] = None
    question_type: str
    question_difficulty: int
    do_stu_answer: str


class ExerciseRecordResponse(BaseModel):
    do_id: int
    question_id: int
    stu_id: int
    kg_id: Optional[int] = None
    course_id: Optional[int] = None
    kg_node_name: Optional[str] = None
    question_type: Optional[str] = None
    question_difficulty: Optional[int] = None
    do_stu_answer: str
    do_score: Optional[float] = None
    do_isTrue: Optional[bool] = None
    iserror_firstly: Optional[bool] = None
    created_at: datetime
    class Config:
        from_attributes = True


class ExerciseRecordListResponse(BaseModel):
    """做题记录列表响应（含题目题干和学科名称）"""
    do_id: int
    question_id: int
    question_description: str
    course_name: Optional[str] = None
    question_type: Optional[str] = None
    question_difficulty: Optional[int] = None
    do_stu_answer: str
    do_score: Optional[float] = None
    do_isTrue: Optional[bool] = None
    kg_node_name: Optional[str] = None
    created_at: datetime
    class Config:
        from_attributes = True
