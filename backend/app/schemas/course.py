"""Course Pydantic 请求/响应模型"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class CourseCreate(BaseModel):
    course_name: str
    course_description: Optional[str] = None
    kg_id: Optional[int] = None


class CourseUpdate(BaseModel):
    course_name: Optional[str] = None
    course_description: Optional[str] = None
    kg_id: Optional[int] = None


class CourseResponse(BaseModel):
    course_id: int
    course_name: str
    course_description: Optional[str] = None
    kg_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    class Config:
        from_attributes = True
