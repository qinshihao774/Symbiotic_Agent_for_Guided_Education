"""OCR 网关 — 代理转发到 ai/ 服务的 OCR 模块"""

import httpx
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse, Response

from app.core.config import settings

router = APIRouter()


def _ai_headers() -> dict[str, str]:
    """构造转发到 AI 引擎的请求头（含服务间认证 token）"""
    return {"X-Service-Token": settings.AI_SERVICE_TOKEN}


@router.post("/tasks")
async def create_ocr_task(
    files: list[UploadFile] = File(..., description="PDF 或图片文件"),
    lang: str = Form(default="ch", description="语言 (ch/en/japan/korean)"),
    formula_enable: bool = Form(default=True, description="启用公式解析"),
    table_enable: bool = Form(default=True, description="启用表格解析"),
    start_page_id: int = Form(default=0, description="起始页 (从 0 开始)"),
    end_page_id: int = Form(default=-1, description="结束页 (-1 表示全部)"),
):
    """提交 OCR 解析任务 — 转发到 AI 引擎"""
    async with httpx.AsyncClient(timeout=120.0) as client:
        # 构造 multipart/form-data
        form_data = {
            "lang": (None, lang),
            "formula_enable": (None, str(formula_enable)),
            "table_enable": (None, str(table_enable)),
            "start_page_id": (None, str(start_page_id)),
            "end_page_id": (None, str(end_page_id)),
        }
        file_parts = []
        for f in files:
            content = await f.read()
            file_parts.append(("files", (f.filename, content, f.content_type)))

        response = await client.post(
            f"{settings.AI_SERVICE_URL}/ocr/tasks",
            headers=_ai_headers(),
            data=form_data,
            files=file_parts,
        )
        response.raise_for_status()
        return response.json()


@router.get("/tasks/{task_id}")
async def get_ocr_task_status(task_id: str):
    """查询 OCR 任务状态 — 转发到 AI 引擎"""
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"{settings.AI_SERVICE_URL}/ocr/tasks/{task_id}",
            headers=_ai_headers(),
        )
        response.raise_for_status()
        return response.json()


@router.get("/tasks/{task_id}/result")
async def get_ocr_task_result(task_id: str):
    """获取 OCR 解析结果 ZIP — 转发到 AI 引擎"""
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.get(
            f"{settings.AI_SERVICE_URL}/ocr/tasks/{task_id}/result",
            headers=_ai_headers(),
        )
        return Response(
            content=response.content,
            status_code=response.status_code,
            media_type="application/zip",
            headers={
                "Content-Disposition": f'attachment; filename="{task_id}.zip"'
            },
        )
