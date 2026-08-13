"""题目练习路由"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.deps import get_current_user_optional
from app.schemas.practice import (
    QuestionCreate,
    QuestionResponse,
    ExerciseRecordCreate,
    ExerciseRecordResponse,
    ExerciseRecordListResponse,
)
from app.schemas.course import CourseResponse
from app.services.practice_service import PracticeService
from app.services.course_service import CourseService

router = APIRouter()


@router.get("/courses", response_model=list[CourseResponse])
async def list_courses(db: AsyncSession = Depends(get_db)):
    service = CourseService()
    return await service.list_courses(db)


@router.get("/questions", response_model=list[QuestionResponse])
async def list_questions(
    course_id: Optional[int] = Query(None),
    kg_node_name: Optional[str] = Query(None),
    difficulty: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    service = PracticeService()
    return await service.list_questions(db, course_id, kg_node_name, difficulty)


@router.get("/questions/{question_id}", response_model=QuestionResponse)
async def get_question(question_id: int, db: AsyncSession = Depends(get_db)):
    service = PracticeService()
    result = await service.get_question_by_id(question_id, db)
    if result is None:
        raise HTTPException(status_code=404, detail="题目不存在")
    return result


@router.post("/submit", response_model=ExerciseRecordResponse)
async def submit_answer(
    data: ExerciseRecordCreate,
    current_user: dict = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    stu_id = current_user.get("id")
    service = PracticeService()
    try:
        return await service.submit_exercise(stu_id, data, db)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/exercise-records", response_model=list[ExerciseRecordListResponse])
async def get_exercise_records(
    course_id: Optional[int] = Query(None),
    wrong_only: Optional[bool] = Query(False),
    current_user: dict = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    """获取当前学生的做题记录。

    - 不传 course_id：获取所有记录
    - 传 course_id：获取指定学科下的记录
    - wrong_only=true：仅获取错题记录（需同时传 course_id）
    """
    stu_id = current_user.get("id")
    service = PracticeService()

    if course_id is not None and wrong_only:
        return await service.get_student_wrong_records_by_course(stu_id, course_id, db)
    elif course_id is not None:
        return await service.get_student_exercise_records_by_course(stu_id, course_id, db)
    else:
        return await service.get_student_exercise_records(stu_id, db)


@router.get("/wrong-records/grouped")
async def get_wrong_records_grouped(
    current_user: dict = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    """获取当前学生按学科分组的错题记录。

    返回格式：{ course_id: { course_name, records: [...] } }
    """
    stu_id = current_user.get("id")
    service = PracticeService()
    return await service.get_student_wrong_records_grouped(stu_id, db)


@router.get("/dashboard/new-question")
async def get_dashboard_new_question(
    course_id: int = Query(...),
    current_user: dict = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    """获取指定学科下、不在学生做题记录中的随机一道题（仪表盘"跳转练习"用）

    返回：
    - question: 随机抽取的题目详情
    - random_index: 该题目在 id_list 中的索引
    - id_list: 该学科下所有题目的 ID 数组（全量 ID 缓存，供前端前后切换）
    """
    stu_id = current_user.get("id")
    service = PracticeService()
    question = await service.get_random_new_question(stu_id, course_id, db)
    if question is None:
        return {"question": None, "random_index": -1, "id_list": []}
    # 获取该学科下所有题目 ID 列表（全量 ID 缓存）
    id_list = await service.get_question_ids_by_course(course_id, db)
    # 找到随机题目的索引
    try:
        random_index = id_list.index(question.question_id)
    except ValueError:
        random_index = 0
    return {"question": question.model_dump(), "random_index": random_index, "id_list": id_list}


@router.get("/dashboard/record-question")
async def get_dashboard_record_question(
    course_id: int = Query(...),
    current_user: dict = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    """获取指定学科下、学生做题记录中的随机一道题（仪表盘"做题记录"用）

    返回：
    - question: 随机抽取的题目详情
    - random_index: 该题目在 id_list 中的索引
    - id_list: 该学科做题记录中所有题目的 ID 数组（全量 ID 缓存，供前端前后切换）
    """
    stu_id = current_user.get("id")
    service = PracticeService()
    question = await service.get_random_record_question(stu_id, course_id, db)
    if question is None:
        return {"question": None, "random_index": -1, "id_list": []}
    # 获取该学科做题记录中所有题目 ID 列表（全量 ID 缓存）
    id_list = await service.get_record_question_ids_by_course(stu_id, course_id, db)
    # 找到随机题目的索引
    try:
        random_index = id_list.index(question.question_id)
    except ValueError:
        random_index = 0
    return {"question": question.model_dump(), "random_index": random_index, "id_list": id_list}


@router.get("/exercise-records/analytics")
async def get_exercise_records_analytics():
    return {"message": "analytics endpoint - not in scope"}


@router.post("/hint")
async def get_hint():
    return {"message": "hint endpoint - not in scope"}
