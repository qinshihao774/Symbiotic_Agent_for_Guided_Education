"""教师建议与评价 API 路由

通过专职 ReAct Agent（react-observation 架构，temperature=0.2）为教师生成对单个学生的建议与评价。

评估依据两个维度（各占 1/2 权重，动态调整）：
1. 学生当下学科的知识图谱进度（知识点掌握程度、学科掌握程度）
2. 学生的 AI 评级（students.stu_level）

兜底机制：
- 数据库异常 → 返回 db_error，前端显示用户友好错误
- 可用维度 <1 → 返回 insufficient，前端友好提示缺失维度及原因
- 可用维度 ≥1 → 生成建议与评价（权重动态调整为 1/N）

落库机制：
- 教师保存评价时，将评价内容写入 evaluation_analysis 表（ea_description 字段）。
"""
import json
import logging

from fastapi import APIRouter, Body, Depends, HTTPException, Query

from app.agent.stu_evaluation_agent import generate_stu_evaluation
from app.agent.tools._base import get_conn
from app.dependencies import verify_service_token

logger = logging.getLogger(__name__)

router = APIRouter()
auth_dep = [Depends(verify_service_token)]


def _persist_evaluation(
    stu_id: int,
    publisher_id: int | None,
    publisher_name: str,
    ea_description: str,
) -> None:
    """将教师保存的评价写入 evaluation_analysis 表。

    严格遵循建表脚本（001_create_tables.sql #11）：
      evaluation_analysis(ea_id, stu_id, publisher_id, publisher_name, ea_description, created_at, updated_at)

    落库失败仅记录日志，不影响接口返回。
    """
    try:
        conn = get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO evaluation_analysis
                        (stu_id, publisher_id, publisher_name, ea_description)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (stu_id, publisher_id, publisher_name, ea_description),
                )
        finally:
            conn.close()
        logger.info(
            f"[StuEvaluation API] 已落库教师评价: stu_id={stu_id}, "
            f"publisher_id={publisher_id}, publisher_name={publisher_name}"
        )
    except Exception as e:
        logger.error(
            f"[StuEvaluation API] 落库教师评价失败 stu_id={stu_id}: {e}",
            exc_info=True,
        )


@router.post("/stu_evaluation")
async def stu_evaluation(
    stu_id: int = Query(..., description="学生 ID", ge=1),
    course_id: int = Query(..., description="学科 ID", ge=1),
    course_name: str | None = Query(None, description="学科名称（可选）"),
):
    """为某学生在某学科下生成教师建议与评价（专职 ReAct Agent）

    综合两个维度数据（学生 AI 评级、知识图谱进度），各维度等权（2 维各 1/2），
    缺失维度时动态调整权重并触发兜底机制。

    Args:
        stu_id: 学生 ID（通过查询参数传入，如 ?stu_id=1）
        course_id: 学科 ID（通过查询参数传入，如 ?course_id=1）
        course_name: 学科名称（可选）
    """
    logger.info(
        f"[StuEvaluation API] 收到教师建议与评价请求: "
        f"stu_id={stu_id}, course_id={course_id}"
    )
    try:
        result = await generate_stu_evaluation(stu_id, course_id, course_name)
        logger.info(
            f"[StuEvaluation API] 教师建议与评价完成: stu_id={stu_id}, "
            f"course_id={course_id}, status={result.get('status')}"
        )
        return result
    except Exception as e:
        logger.error(
            f"[StuEvaluation API] 教师建议与评价失败: stu_id={stu_id}, "
            f"course_id={course_id}, error={e}",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail=f"教师建议与评价服务异常: {str(e)}")


@router.post("/stu_evaluation/save")
async def save_stu_evaluation(
    payload: dict = Body(...),
):
    """保存教师对某学生的评价到 evaluation_analysis 表。

    Body 结构：
    {
        "stu_id": int,
        "publisher_id": int | None,   # 教师 tea_id
        "publisher_name": str,        # 教师 tea_name
        "ea_description": str         # 评价内容
    }
    """
    stu_id = payload.get("stu_id")
    publisher_id = payload.get("publisher_id")
    publisher_name = payload.get("publisher_name", "")
    ea_description = payload.get("ea_description", "")

    if not stu_id:
        raise HTTPException(status_code=400, detail="缺少 stu_id 参数")
    if not publisher_name:
        raise HTTPException(status_code=400, detail="缺少 publisher_name 参数")
    if not ea_description:
        raise HTTPException(status_code=400, detail="评价内容不能为空")

    logger.info(
        f"[StuEvaluation API] 收到保存教师评价请求: "
        f"stu_id={stu_id}, publisher_id={publisher_id}, publisher_name={publisher_name}"
    )
    try:
        _persist_evaluation(stu_id, publisher_id, publisher_name, ea_description)
        return {"success": True, "message": "评价已保存"}
    except Exception as e:
        logger.error(
            f"[StuEvaluation API] 保存教师评价失败: stu_id={stu_id}, error={e}",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail=f"保存教师评价失败: {str(e)}")
