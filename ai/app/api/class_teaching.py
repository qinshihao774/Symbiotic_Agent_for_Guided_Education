"""班级教学建议 API 路由

通过 ReAct Agent 为教师生成班级教学建议。

建议依据三个维度（各占 1/3 权重，动态调整）：
1. 学生评级分布       (students.stu_level，按班级聚合)
2. 班级知识点平均掌握度进度 (student_knowledge_mastery / student_course_mastery，按班级聚合)
3. 疑难章节与知识点   (exercise_records 错题，按班级聚合；疑难章节与知识点视为同一维度)

兜底机制：
- 数据库异常 → 返回 db_error，前端显示用户友好错误
- 可用维度 <2 → 返回 insufficient，前端友好提示缺失维度及原因
- 可用维度 ≥2 → 生成教学建议（权重动态调整为 1/N：3 维各 1/3，2 维各 1/2）
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, Query

from app.agent.class_teaching_agent import generate_class_teaching_suggestion
from app.dependencies import verify_service_token

logger = logging.getLogger(__name__)

router = APIRouter()
auth_dep = [Depends(verify_service_token)]


@router.post("/class_teaching_suggestion")
async def class_teaching_suggestion(
    class_id: int = Query(..., description="班级 ID", ge=1),
    course_id: int = Query(..., description="学科 ID", ge=1),
    course_name: str | None = Query(None, description="学科名称（可选）"),
):
    """为某班级在某学科下生成教学建议（ReAct Agent）

    综合三个维度数据（学生评级、班级知识点平均掌握度进度、疑难章节与知识点），
    各维度等权（3 维各 1/3，2 维各 1/2），缺失维度时动态调整权重并触发兜底机制。

    Args:
        class_id: 班级 ID（通过查询参数传入，如 ?class_id=1）
        course_id: 学科 ID（通过查询参数传入，如 ?course_id=1）
        course_name: 学科名称（可选）
    """
    logger.info(
        f"[ClassTeaching API] 收到班级教学建议请求: "
        f"class_id={class_id}, course_id={course_id}"
    )
    try:
        result = await generate_class_teaching_suggestion(
            class_id, course_id, course_name
        )
        logger.info(
            f"[ClassTeaching API] 班级教学建议完成: class_id={class_id}, "
            f"course_id={course_id}, status={result.get('status')}"
        )
        return result
    except Exception as e:
        logger.error(
            f"[ClassTeaching API] 班级教学建议失败: class_id={class_id}, "
            f"course_id={course_id}, error={e}",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail=f"班级教学建议服务异常: {str(e)}")
