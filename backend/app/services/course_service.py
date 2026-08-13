"""Course 业务逻辑层"""
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.course import Course
from app.schemas.course import CourseCreate, CourseUpdate, CourseResponse


class CourseService:
    async def create_course(self, data: CourseCreate, db: AsyncSession) -> CourseResponse:
        course = Course(course_name=data.course_name, course_description=data.course_description, kg_id=data.kg_id)
        db.add(course)
        await db.commit()
        await db.refresh(course)
        return CourseResponse.model_validate(course)

    async def list_courses(self, db: AsyncSession) -> list[CourseResponse]:
        result = await db.execute(select(Course).order_by(Course.course_id))
        courses = result.scalars().all()
        return [CourseResponse.model_validate(c) for c in courses]

    async def get_course_by_id(self, course_id: int, db: AsyncSession) -> Optional[CourseResponse]:
        result = await db.execute(select(Course).where(Course.course_id == course_id))
        course = result.scalar_one_or_none()
        if course is None:
            return None
        return CourseResponse.model_validate(course)

    async def update_course(self, course_id: int, data: CourseUpdate, db: AsyncSession) -> Optional[CourseResponse]:
        result = await db.execute(select(Course).where(Course.course_id == course_id))
        course = result.scalar_one_or_none()
        if course is None:
            return None
        if data.course_name is not None:
            course.course_name = data.course_name
        if data.course_description is not None:
            course.course_description = data.course_description
        if data.kg_id is not None:
            course.kg_id = data.kg_id
        await db.commit()
        await db.refresh(course)
        return CourseResponse.model_validate(course)

    async def delete_course(self, course_id: int, db: AsyncSession) -> bool:
        result = await db.execute(select(Course).where(Course.course_id == course_id))
        course = result.scalar_one_or_none()
        if course is None:
            return False
        await db.delete(course)
        await db.commit()
        return True
