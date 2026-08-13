"""OCR 路由 — 文档解析 API 端点"""

import os
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse

from app.ocr.schemas import OcrParseParams, TaskStatusResponse, TaskSubmitResponse
from app.ocr.service import save_upload_files

router = APIRouter()

# 全局任务管理器引用，由 main.py 在 lifespan 中设置
_task_manager = None


def get_task_manager():
    if _task_manager is None:
        raise HTTPException(status_code=503, detail="OCR task manager not initialized")
    return _task_manager


def set_task_manager(manager):
    global _task_manager
    _task_manager = manager


@router.post("/tasks", status_code=202, response_model=TaskSubmitResponse)
async def submit_task(
    files: Annotated[list[UploadFile], File(description="PDF 或图片文件")],
    lang: Annotated[str, Form(description="语言 (ch/en/japan/korean)")] = "ch",
    formula_enable: Annotated[bool, Form(description="启用公式解析")] = True,
    table_enable: Annotated[bool, Form(description="启用表格解析")] = True,
    start_page_id: Annotated[int, Form(description="起始页 (从 0 开始)")] = 0,
    end_page_id: Annotated[int, Form(description="结束页 (-1 表示全部)")] = -1,
):
    """提交 OCR 解析任务"""
    task_manager = get_task_manager()

    # 保存上传文件
    upload_dir = f"{task_manager._get_output_root()}/uploads/{os.urandom(8).hex()}"
    try:
        uploads = await save_upload_files(upload_dir, files)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not uploads:
        raise HTTPException(status_code=400, detail="No valid files uploaded")

    params = OcrParseParams(
        lang=lang,
        formula_enable=formula_enable,
        table_enable=table_enable,
        start_page_id=start_page_id,
        end_page_id=end_page_id if end_page_id >= 0 else 99999,
    )

    task = await task_manager.submit(
        file_names=[u.stem for u in uploads],
        upload_names=[u.original_name for u in uploads],
        uploads=[u.path for u in uploads],
        params=params,
    )

    return TaskSubmitResponse(
        task_id=task.task_id,
        status=task.status,
        status_url=f"/ocr/tasks/{task.task_id}",
        result_url=f"/ocr/tasks/{task.task_id}/result",
    )


@router.get("/tasks/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(task_id: str):
    """查询 OCR 任务状态"""
    task_manager = get_task_manager()
    task = task_manager.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task_manager.get_status_payload(task)


@router.get("/tasks/{task_id}/result")
async def get_task_result(task_id: str):
    """获取 OCR 解析结果"""
    task_manager = get_task_manager()
    task = task_manager.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.status in ("pending", "processing"):
        return JSONResponse(
            status_code=202,
            content={
                **task_manager.get_status_payload(task),
                "message": "Task result is not ready yet",
            },
        )

    if task.status == "failed":
        return JSONResponse(
            status_code=409,
            content={
                **task_manager.get_status_payload(task),
                "message": "Task execution failed",
            },
        )

    # 生成 ZIP 并返回
    try:
        zip_path = task_manager.get_result_zip_path(task)
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to create result ZIP: {exc}"
        ) from exc

    return FileResponse(
        path=zip_path,
        media_type="application/zip",
        filename=f"{task_id}.zip",
    )
