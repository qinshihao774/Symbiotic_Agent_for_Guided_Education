"""学生 AI 学习分析 API 路由

通过 ReAct Agent 对学生进行多维度的 AI 学习分析：
- 维度 1: 个人评级（students.stu_level）
- 维度 2: 知识图谱掌握度（student_knowledge_mastery）
- 维度 3: 错题记录及知识点分布（exercise_records + questions）

Agent 会自主调用数据查询工具，观察结果后进行综合分析。
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, Query

from app.agent.stu_analysis_agent import analyze_student
from app.dependencies import verify_service_token

logger = logging.getLogger(__name__)

router = APIRouter()
auth_dep = [Depends(verify_service_token)]


@router.post("/stu_analysis")
async def stu_analysis(
    stu_id: int = Query(..., description="学生 ID", ge=1),
):
    """学生 AI 学习分析（ReAct Agent）

    基于三个维度（知识图谱掌握度、错题记录、个人评级）
    通过 ReAct Agent 自主收集数据并生成综合分析报告。

    Agent 工作方式：
    1. 接收学生 ID
    2. 自主决定调用哪些数据查询工具、以什么顺序调用
    3. 观察每个工具返回的结果，动态调整分析策略
    4. 综合所有可用数据，输出结构化分析报告

    Args:
        stu_id: 学生 ID（通过查询参数传入，如 ?stu_id=1）
    """
    logger.info(f"[Analysis API] 收到分析请求: stu_id={stu_id}")
    try:
        result = await analyze_student(stu_id)
        logger.info(
            f"[Analysis API] 分析完成: stu_id={stu_id}, "
            f"dimensions_available={result.get('dimensions_available', 0)}"
        )
        return result
    except Exception as e:
        logger.error(f"[Analysis API] 分析失败: stu_id={stu_id}, error={e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"AI 分析服务异常: {str(e)}")
