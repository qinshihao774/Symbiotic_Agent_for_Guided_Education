"""AI 题目分析与解惑路由"""

import logging
from typing import Optional

from fastapi import APIRouter, Query

from app.agent.question_analysis_agent import analyze_question

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/question")
async def question_analysis(
    question_id: int = Query(..., description="题目 ID", ge=1),
    do_stu_answer: Optional[str] = Query(None, description="学生提交的答案（do_stu_answer），用于个性化作答剖析"),
    stu_id: Optional[str] = Query(None, description="学生 ID，可选，用于兜底查询该学生最近一次作答"),
):
    """对指定题目进行 AI 分析与解惑

    双维度：题目答案深度剖析 + 知识图谱局部网络视角；
    并结合学生提交的答案（do_stu_answer）进行个性化作答剖析。
    """
    # 前端可能将 undefined 序列化为空字符串，需容错处理
    stu_id_int = None
    if stu_id:
        try:
            stu_id_int = int(stu_id)
        except (TypeError, ValueError):
            stu_id_int = None

    result = await analyze_question(
        question_id,
        do_stu_answer=do_stu_answer,
        stu_id=stu_id_int,
    )
    return result
