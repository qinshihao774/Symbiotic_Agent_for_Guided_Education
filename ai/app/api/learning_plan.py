"""学习规划 API 路由

通过 ReAct Agent 为每门学科分别制定学习规划。

规划依据四个维度（各占 25% 权重，动态调整）：
1. 学生端 AI 分析内容   (evaluation_analysis 中 publisher_name='AI')
2. 学生自身知识图谱     (student_knowledge_mastery，按学科 kg_id 过滤)
3. 习题情况             (exercise_records，按学科 course_id 过滤)
4. 老师意见与评估       (evaluation_analysis 中 publisher_name != 'AI')

兜底机制：
- 数据库异常 → 返回 db_error，前端显示用户友好错误
- 可用维度 ≤2 → 返回 insufficient，前端提示缺失维度
- 可用维度 ≥3 → 生成细粒度规划（权重动态调整为 1/N）
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, Query

from app.agent.learning_plan_agent import generate_learning_plan
from app.dependencies import verify_service_token

logger = logging.getLogger(__name__)

router = APIRouter()
auth_dep = [Depends(verify_service_token)]


@router.post("/learning_plan")
async def learning_plan(
    stu_id: int = Query(..., description="学生 ID", ge=1),
):
    """为某学生生成各学科学习规划（ReAct Agent）

    为 courses 表中的每门学科分别制定学习规划，综合四个维度数据，
    各维度等权（25%），缺失维度时动态调整权重并触发兜底机制。

    Args:
        stu_id: 学生 ID（通过查询参数传入，如 ?stu_id=1）
    """
    logger.info(f"[LearningPlan API] 收到学习规划请求: stu_id={stu_id}")
    try:
        result = await generate_learning_plan(stu_id)
        logger.info(
            f"[LearningPlan API] 学习规划完成: stu_id={stu_id}, "
            f"subjects={len(result.get('subjects', []))}"
        )
        return result
    except Exception as e:
        logger.error(
            f"[LearningPlan API] 学习规划失败: stu_id={stu_id}, error={e}",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail=f"学习规划服务异常: {str(e)}")
