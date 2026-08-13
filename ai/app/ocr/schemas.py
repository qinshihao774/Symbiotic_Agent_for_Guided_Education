"""OCR 模块的数据模型"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel


@dataclass
class StoredUpload:
    """已保存的上传文件信息"""
    original_name: str
    stem: str
    path: str


class TaskSubmitResponse(BaseModel):
    """任务提交响应"""
    task_id: str
    status: str
    status_url: str
    result_url: str


class TaskStatusResponse(BaseModel):
    """任务状态响应"""
    task_id: str
    status: str
    file_names: list[str]
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error: Optional[str] = None


@dataclass
class OcrParseParams:
    """OCR 解析参数"""
    lang: str = "ch"
    formula_enable: bool = True
    table_enable: bool = True
    start_page_id: int = 0
    end_page_id: int = 99999


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
