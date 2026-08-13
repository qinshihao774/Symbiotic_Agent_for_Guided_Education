"""Auth Pydantic 请求/响应模型"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class StudentRegisterRequest(BaseModel):
    stu_name: str
    stu_email: Optional[str] = None
    stu_pwd: Optional[str] = None
    stu_gender: Optional[str] = None


class TeacherRegisterRequest(BaseModel):
    tea_name: str
    tea_email: Optional[str] = None
    tea_pwd: Optional[str] = None


class LoginRequest(BaseModel):
    email: str
    password: str
    user_type: str  # "student" or "teacher"


class StudentResponse(BaseModel):
    stu_id: int
    stu_name: str
    stu_gender: Optional[str] = None
    stu_email: Optional[str] = None
    stu_level: Optional[str] = None
    class_id: Optional[int] = None
    created_at: datetime
    class Config:
        from_attributes = True


class TeacherResponse(BaseModel):
    tea_id: int
    tea_name: str
    tea_email: Optional[str] = None
    created_at: datetime
    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_type: str
    user_id: int
    user_name: str
    user_email: Optional[str] = None


class StudentUpdateRequest(BaseModel):
    """学生个人信息更新请求——所有字段可选，只更新传入的字段"""
    stu_name: Optional[str] = None
    stu_email: Optional[str] = None
    stu_pwd: Optional[str] = None
    stu_gender: Optional[str] = None
