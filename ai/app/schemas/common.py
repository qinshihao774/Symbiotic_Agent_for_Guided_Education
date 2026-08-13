"""通用响应模型"""

from pydantic import BaseModel


class TaskSubmitResponse(BaseModel):
    task_id: str
    status: str = "queued"


class TaskStatusResponse(BaseModel):
    task_id: str
    status: str  # "queued" | "running" | "completed" | "failed"
    result: dict | None = None
    error: str | None = None
