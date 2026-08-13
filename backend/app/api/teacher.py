"""Teacher management routes."""
from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.services.teacher_service import TeacherService

router = APIRouter()


@router.get("/courses")
async def list_teacher_courses(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[dict]:
    """Get the subjects taught by the current teacher."""
    if current_user["user_type"] != "teacher":
        return []

    service = TeacherService()
    return await service.get_teacher_courses(current_user["id"], db)


@router.get("/courses/{course_id}/chapters")
async def list_course_chapters(
    course_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[dict]:
    """Get the knowledge-graph chapters of a subject taught by the current teacher."""
    if current_user["user_type"] != "teacher":
        return []

    service = TeacherService()
    return await service.get_course_chapters(current_user["id"], course_id, db)


@router.get("/classes")
async def list_teacher_classes(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[dict]:
    """Get the classes managed by the current teacher."""
    if current_user["user_type"] != "teacher":
        return []

    service = TeacherService()
    return await service.get_teacher_classes(current_user["id"], db)


@router.get("/classes/{class_id}/students")
async def list_class_students(
    class_id: int,
    course_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[dict]:
    """Get the students in a class for the selected subject."""
    if current_user["user_type"] != "teacher":
        return []

    service = TeacherService()
    return await service.get_class_students(current_user["id"], class_id, course_id, db)


@router.get("/classes/{class_id}/difficult-knowledge")
async def list_difficult_knowledge(
    class_id: int,
    course_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[dict]:
    """Get difficult knowledge point word-cloud data for a class and subject."""
    if current_user["user_type"] != "teacher":
        return []

    service = TeacherService()
    return await service.get_difficult_knowledge_points(
        current_user["id"], class_id, course_id, db
    )


@router.get("/classes/{class_id}/difficult-chapters")
async def list_difficult_chapters(
    class_id: int,
    course_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[dict]:
    """Get difficult-chapter pie-chart data for a class and subject.

    统计该班级该学科下所有学生错题知识点，归类到知识图谱顶层章节后返回分布占比。
    """
    if current_user["user_type"] != "teacher":
        return []

    service = TeacherService()
    return await service.get_difficult_chapters(
        current_user["id"], class_id, course_id, db
    )


@router.get("/classes/{class_id}/teaching-suggestion")
async def get_class_teaching_suggestion(
    class_id: int,
    course_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """生成班级教学建议（AI ReAct Agent，三维度评估）。

    综合三个维度（学生评级、班级知识点平均掌握度进度、疑难章节与知识点），
    各维度等权（3 维各 1/3，2 维各 1/2），缺失维度时触发兜底机制。
    """
    if current_user["user_type"] != "teacher":
        return {
            "status": "db_error",
            "error": "no_access",
            "error_message": "仅教师可访问班级教学建议。",
            "suggestion": None,
        }

    service = TeacherService()
    return await service.get_class_teaching_suggestion(
        current_user["id"], class_id, course_id, db
    )


@router.get("/analytics/{class_id}")
async def get_class_analytics(class_id: int):
    """Get the class analytics report."""
    pass


@router.get("/alerts")
async def get_learning_alerts():
    """Get learning risk alerts."""
    pass


@router.get("/students/{student_id}/knowledge-graph")
async def get_student_knowledge_graph(
    student_id: int,
    course_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """获取某学生在某学科下的个人知识图谱（图数据 + 掌握度层级树）。

    严格对应关系：当前教师必须同时教授该学生所在班级与该学科，
    否则返回空结果，防止越权查看其他班级/学科学生的知识图谱。
    """
    if current_user["user_type"] != "teacher":
        return {}

    service = TeacherService()
    return await service.get_student_knowledge_graph(
        current_user["id"], student_id, course_id, db
    )


@router.get("/students/{student_id}/profile")
async def get_student_profile(student_id: int):
    """Get a student profile."""
    pass


@router.post("/assignments")
async def create_assignment():
    """Publish an assignment or exam."""
    pass


@router.get("/assignments/{assignment_id}/results")
async def get_assignment_results(assignment_id: int):
    """Get assignment grading results."""
    pass
