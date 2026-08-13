"""学习管理路由"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.deps import get_current_user_optional
from app.schemas.learning import (
    StudentCourseMasteryCreate, StudentCourseMasteryResponse,
    StudentKnowledgeMasteryCreate, StudentKnowledgeMasteryResponse,
)
from app.services.learning_service import LearningService
from app.services.mastery_service import MasteryService

router = APIRouter()


@router.get("/dashboard")
async def get_learning_dashboard():
    return {"message": "dashboard endpoint - not in scope"}


@router.get("/plan")
async def get_learning_plan():
    return {"message": "plan endpoint - not in scope"}


@router.post("/plan/generate")
async def generate_learning_plan():
    return {"message": "plan generate endpoint - not in scope"}


@router.get("/progress")
async def get_learning_progress(
    current_user: dict = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    stu_id = current_user.get("id")
    service = LearningService()
    course_mastery = await service.get_student_course_mastery(stu_id, db)
    knowledge_mastery = await service.get_student_knowledge_mastery(stu_id, db)
    return {"course_mastery": course_mastery, "knowledge_mastery": knowledge_mastery}


@router.get("/history")
async def get_learning_history():
    return {"message": "history endpoint - not in scope"}

@router.get("/dashboard-progress")
async def get_dashboard_progress(
    current_user: dict = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    """
    Return course_process for each course of the current student.
    Format: { course_id: course_process, ... }
    course_process is null-safe, returns 0.
    """
    stu_id = current_user.get("id")
    service = LearningService()
    course_masteries = await service.get_student_course_mastery(stu_id, db)
    return {str(m.course_id): m.course_process if m.course_process is not None else 0.0 for m in course_masteries}


@router.post("/mastery/course", response_model=StudentCourseMasteryResponse)
async def set_course_mastery(
    data: StudentCourseMasteryCreate,
    current_user: dict = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    stu_id = current_user.get("id")
    service = LearningService()
    return await service.set_course_mastery(stu_id, data, db)


@router.post("/mastery/knowledge", response_model=StudentKnowledgeMasteryResponse)
async def set_knowledge_mastery(
    data: StudentKnowledgeMasteryCreate,
    current_user: dict = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    stu_id = current_user.get("id")
    service = LearningService()
    return await service.set_knowledge_mastery(stu_id, data, db)


@router.get("/mastery/hierarchy")
async def get_mastery_hierarchy(
    course_id: int = Query(..., description="学科 ID"),
    current_user: dict = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    """获取某学科下学生的掌握度层级树（学科→章节→小节→知识点）。

    掌握度由做题记录自动聚合：
    - 知识点掌握度：做题时更新（客观题 5/0 分，主观题按得分映射，加权平均）
    - 小节掌握度 = 该小节下所有知识点掌握度的平均值
    - 章节掌握度 = 该章节下所有小节掌握度的平均值
    - 学科掌握度 = 该学科下所有知识点掌握度的平均值
    """
    stu_id = current_user.get("id")
    service = MasteryService()
    return await service.get_mastery_hierarchy(stu_id, course_id, db)
