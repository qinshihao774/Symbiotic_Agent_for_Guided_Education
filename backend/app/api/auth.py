"""用户认证路由"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.deps import get_current_user
from app.schemas.auth import (
    StudentRegisterRequest, TeacherRegisterRequest,
    LoginRequest, StudentResponse, TeacherResponse, TokenResponse,
    StudentUpdateRequest,
)
from app.services.auth_service import AuthService

router = APIRouter()


@router.post("/register/student", response_model=StudentResponse)
async def register_student(data: StudentRegisterRequest, db: AsyncSession = Depends(get_db)):
    service = AuthService()
    return await service.register_student(data, db)


@router.post("/register/teacher", response_model=TeacherResponse)
async def register_teacher(data: TeacherRegisterRequest, db: AsyncSession = Depends(get_db)):
    service = AuthService()
    return await service.register_teacher(data, db)


@router.post("/login", response_model=TokenResponse)
async def login(data: LoginRequest, db: AsyncSession = Depends(get_db)):
    service = AuthService()
    result = await service.login(data.email, data.password, data.user_type, db)
    if result is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="邮箱或密码错误")
    return result


@router.get("/me")
async def get_current_user_info(current_user: dict = Depends(get_current_user)):
    """获取当前登录用户的完整信息（姓名、邮箱、性别等）"""
    return current_user


@router.put("/profile", response_model=StudentResponse)
async def update_profile(
    data: StudentUpdateRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新当前登录学生的个人信息（姓名、邮箱、密码、性别）"""
    if current_user["user_type"] != "student":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="仅学生用户可以编辑个人信息")
    service = AuthService()
    updated = await service.update_student(current_user["id"], data, db)
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    return updated
