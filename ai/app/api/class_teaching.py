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

落库机制：
- 生成成功（status=ok）时，将班级 AI 评级（ai_level）、AI 教学建议（ai_suggestion，JSON 文本）、
  知识点平均掌握度（course_avg_process）写入 classes 表对应字段，并同步更新 updated_at。
"""
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Query

from app.agent.class_teaching_agent import generate_class_teaching_suggestion
from app.agent.tools._base import get_conn
from app.dependencies import verify_service_token

logger = logging.getLogger(__name__)

router = APIRouter()
auth_dep = [Depends(verify_service_token)]


def _persist_class_ai_fields(
    class_id: int,
    ai_level: str | None,
    ai_suggestion: dict | None,
    course_avg_process: float | None,
) -> None:
    """将班级 AI 评级、AI 建议、知识点平均掌握度写入 classes 表，并更新 updated_at。

    仅当 ai_level 或 ai_suggestion 或 course_avg_process 至少一项非空时才执行更新，
    避免空值覆盖已有数据。更新失败仅记录日志，不影响接口返回。
    """
    if ai_level is None and ai_suggestion is None and course_avg_process is None:
        return

    try:
        conn = get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE classes
                    SET ai_level = %s,
                        ai_suggestion = %s,
                        course_avg_process = %s,
                        updated_at = now()
                    WHERE class_id = %s
                    """,
                    (
                        ai_level,
                        json.dumps(ai_suggestion, ensure_ascii=False)
                        if ai_suggestion is not None
                        else None,
                        course_avg_process,
                        class_id,
                    ),
                )
        finally:
            conn.close()
        logger.info(
            f"[ClassTeaching API] 已落库班级 AI 字段: class_id={class_id}, "
            f"ai_level={ai_level}, course_avg_process={course_avg_process}"
        )
    except Exception as e:
        logger.error(
            f"[ClassTeaching API] 落库班级 AI 字段失败 class_id={class_id}: {e}",
            exc_info=True,
        )


@router.post("/class_teaching_suggestion")
async def class_teaching_suggestion(
    class_id: int = Query(..., description="班级 ID", ge=1),
    course_id: int = Query(..., description="学科 ID", ge=1),
    course_name: str | None = Query(None, description="学科名称（可选）"),
):
    """为某班级在某学科下生成教学建议（ReAct Agent）

    综合三个维度数据（学生评级、班级知识点平均掌握度进度、疑难章节与知识点），
    各维度等权（3 维各 1/3，2 维各 1/2），缺失维度时动态调整权重并触发兜底机制。

    生成成功（status=ok）时，将班级 AI 评级、AI 建议、知识点平均掌握度落库到 classes 表。

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

        # 生成成功 → 落库班级 AI 字段
        if result.get("status") == "ok":
            _persist_class_ai_fields(
                class_id,
                result.get("ai_level"),
                result.get("suggestion"),
                result.get("course_avg_process"),
            )

        return result
    except Exception as e:
        logger.error(
            f"[ClassTeaching API] 班级教学建议失败: class_id={class_id}, "
            f"course_id={course_id}, error={e}",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail=f"班级教学建议服务异常: {str(e)}")
