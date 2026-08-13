"""AI 简答题（Q_A）评分路由"""

import logging

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.agent.qa_score_agent import score_qa

logger = logging.getLogger(__name__)

router = APIRouter()


class QaScoreRequest(BaseModel):
    question_description: str = Field(..., description="题目题干")
    question_answer: str = Field(..., description="标准答案")
    stu_answer: str = Field(..., description="学生回答")


@router.post("/qa_score")
async def qa_score(req: QaScoreRequest):
    """对简答题作答进行大模型评分（满分 10 分，float）

    根据题目题干、标准答案与学生回答，由大模型酌情给分。
    """
    result = await score_qa(
        req.question_description,
        req.question_answer,
        req.stu_answer,
    )
    return result
