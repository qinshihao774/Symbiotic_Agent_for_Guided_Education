"""Learning 业务逻辑层 — 掌握度管理"""
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.learning import StudentCourseMastery, StudentKnowledgeMastery
from app.schemas.learning import (
    StudentCourseMasteryCreate, StudentCourseMasteryResponse,
    StudentKnowledgeMasteryCreate, StudentKnowledgeMasteryResponse,
)


class LearningService:
    async def set_course_mastery(self, stu_id: int, data: StudentCourseMasteryCreate, db: AsyncSession) -> StudentCourseMasteryResponse:
        result = await db.execute(
            select(StudentCourseMastery).where(
                StudentCourseMastery.stu_id == stu_id,
                StudentCourseMastery.course_id == data.course_id,
            )
        )
        mastery = result.scalar_one_or_none()
        if mastery is None:
            mastery = StudentCourseMastery(stu_id=stu_id, course_id=data.course_id, course_degree=data.course_degree)
            db.add(mastery)
        else:
            mastery.course_degree = data.course_degree
        await db.commit()
        await db.refresh(mastery)
        return StudentCourseMasteryResponse.model_validate(mastery)

    async def get_student_course_mastery(self, stu_id: int, db: AsyncSession) -> list[StudentCourseMasteryResponse]:
        result = await db.execute(select(StudentCourseMastery).where(StudentCourseMastery.stu_id == stu_id))
        masteries = result.scalars().all()
        return [StudentCourseMasteryResponse.model_validate(m) for m in masteries]

    async def set_knowledge_mastery(self, stu_id: int, data: StudentKnowledgeMasteryCreate, db: AsyncSession) -> StudentKnowledgeMasteryResponse:
        result = await db.execute(
            select(StudentKnowledgeMastery).where(
                StudentKnowledgeMastery.stu_id == stu_id,
                StudentKnowledgeMastery.course_id == data.course_id,
                StudentKnowledgeMastery.kg_node_name == data.kg_node_name,
            )
        )
        mastery = result.scalar_one_or_none()
        if mastery is None:
            mastery = StudentKnowledgeMastery(
                stu_id=stu_id,
                course_id=data.course_id,
                kg_node_name=data.kg_node_name,
                kg_degree=data.kg_degree,
            )
            db.add(mastery)
        else:
            mastery.kg_degree = data.kg_degree
        await db.commit()
        await db.refresh(mastery)
        return StudentKnowledgeMasteryResponse.model_validate(mastery)

    async def get_student_knowledge_mastery(self, stu_id: int, db: AsyncSession) -> list[StudentKnowledgeMasteryResponse]:
        result = await db.execute(select(StudentKnowledgeMastery).where(StudentKnowledgeMastery.stu_id == stu_id))
        masteries = result.scalars().all()
        return [StudentKnowledgeMasteryResponse.model_validate(m) for m in masteries]
