"""GNN 请求/响应模型"""

from pydantic import BaseModel


class RecommendRequest(BaseModel):
    student_id: int
    top_k: int = 10


class RecommendResponse(BaseModel):
    questions: list[dict]


class LessonPlanRequest(BaseModel):
    class_id: int
    topic: str


class LessonPlanResponse(BaseModel):
    plan: dict
    references: list[dict]
