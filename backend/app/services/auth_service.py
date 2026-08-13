"""Auth 业务逻辑层"""
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.security import hash_password, verify_password, create_access_token
from app.models.user import Student, Teacher
from app.models.classes import Class
from app.schemas.auth import (
    StudentRegisterRequest, TeacherRegisterRequest,
    StudentResponse, TeacherResponse, TokenResponse,
    StudentUpdateRequest,
)


class AuthService:
    async def register_student(self, data: StudentRegisterRequest, db: AsyncSession) -> StudentResponse:
        hashed = hash_password(data.stu_pwd) if data.stu_pwd else None
        student = Student(
            stu_name=data.stu_name,
            stu_email=data.stu_email,
            stu_pwd=hashed,
            stu_gender=data.stu_gender,
        )
        db.add(student)
        await db.commit()
        await db.refresh(student)
        return StudentResponse.model_validate(student)

    async def register_teacher(self, data: TeacherRegisterRequest, db: AsyncSession) -> TeacherResponse:
        hashed = hash_password(data.tea_pwd) if data.tea_pwd else None
        teacher = Teacher(
            tea_name=data.tea_name,
            tea_email=data.tea_email,
            tea_pwd=hashed,
        )
        db.add(teacher)
        await db.commit()
        await db.refresh(teacher)
        return TeacherResponse.model_validate(teacher)

    async def login(self, email: str, password: str, user_type: str, db: AsyncSession) -> Optional[TokenResponse]:
        if user_type == "student":
            result = await db.execute(select(Student).where(Student.stu_email == email))
            user = result.scalar_one_or_none()
            if user is None or user.stu_pwd is None:
                return None
            if not verify_password(password, user.stu_pwd):
                return None
            token = create_access_token(data={"sub": str(user.stu_id), "user_type": user_type})
            return TokenResponse(
                access_token=token,
                user_type=user_type,
                user_id=user.stu_id,
                user_name=user.stu_name,
                user_email=user.stu_email,
            )
        elif user_type == "teacher":
            result = await db.execute(select(Teacher).where(Teacher.tea_email == email))
            user = result.scalar_one_or_none()
            if user is None or user.tea_pwd is None:
                return None
            if not verify_password(password, user.tea_pwd):
                return None
            token = create_access_token(data={"sub": str(user.tea_id), "user_type": user_type})
            return TokenResponse(
                access_token=token,
                user_type=user_type,
                user_id=user.tea_id,
                user_name=user.tea_name,
                user_email=user.tea_email,
            )
        else:
            return None

    async def get_student_by_id(self, stu_id: int, db: AsyncSession) -> Optional[StudentResponse]:
        result = await db.execute(select(Student).where(Student.stu_id == stu_id))
        student = result.scalar_one_or_none()
        if student is None:
            return None
        return StudentResponse.model_validate(student)

    async def get_class_name(self, class_id: int, db: AsyncSession) -> Optional[str]:
        """根据班级 ID 查询班级名称"""
        result = await db.execute(select(Class).where(Class.class_id == class_id))
        cls = result.scalar_one_or_none()
        if cls is None:
            return None
        return cls.class_name

    async def get_teacher_by_id(self, tea_id: int, db: AsyncSession) -> Optional[TeacherResponse]:
        result = await db.execute(select(Teacher).where(Teacher.tea_id == tea_id))
        teacher = result.scalar_one_or_none()
        if teacher is None:
            return None
        return TeacherResponse.model_validate(teacher)

    async def update_student(self, stu_id: int, data: StudentUpdateRequest, db: AsyncSession) -> Optional[StudentResponse]:
        """更新学生个人信息，只更新传入的非空字段"""
        result = await db.execute(select(Student).where(Student.stu_id == stu_id))
        student = result.scalar_one_or_none()
        if student is None:
            return None

        if data.stu_name is not None:
            student.stu_name = data.stu_name
        if data.stu_email is not None:
            student.stu_email = data.stu_email
        if data.stu_pwd is not None and data.stu_pwd != "":
            student.stu_pwd = hash_password(data.stu_pwd)
        if data.stu_gender is not None:
            student.stu_gender = data.stu_gender

        await db.commit()
        await db.refresh(student)
        return StudentResponse.model_validate(student)
