"""知识图谱网关 — 代理转发到 ai/ 服务的 KG 模块

职责：
  1. POST /build          — 接收文件，创建 KgGraph 元数据，转发到 AI 引擎
  2. GET  /build/status    — 查询构建状态，完成时自动更新 PostgreSQL 统计
  3. GET  /build/result    — 获取构建结果
  4. GET  /graph/data      — 代理查询图数据
  5. GET  /graph/search    — 代理搜索节点
  6. POST /graph/node      — 创建节点
  7. PUT  /graph/node/{id} — 更新节点
  8. DELETE /graph/node/{id} — 删除节点
  9. POST /graph/edge      — 创建边
 10. PUT  /graph/edge      — 更新边
 11. DELETE /graph/edge    — 删除边
"""

import os
import tempfile

import httpx
import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile

from app.core.config import settings
from app.core.database import async_session
from app.core.deps import get_current_user_optional
from app.services.kg_graph_service import KgGraphService

router = APIRouter()

KG_UPLOAD_DIR = os.path.join(tempfile.gettempdir(), "kg_uploads")


def _ai_headers() -> dict[str, str]:
    return {"X-Service-Token": settings.AI_SERVICE_TOKEN}


async def _proxy(request: Request, method: str, path: str, extra_params: dict | None = None):
    """通用代理转发"""
    params = dict(request.query_params)
    if extra_params:
        params.update(extra_params)
    kwargs: dict = {"headers": _ai_headers(), "params": params, "timeout": 60.0}
    if method in ("POST", "PUT"):
        kwargs["json"] = await request.json()

    async with httpx.AsyncClient() as client:
        response = await client.request(method, f"{settings.AI_SERVICE_URL}{path}", **kwargs)
        if response.status_code >= 400:
            detail = response.text
            try:
                detail = response.json().get("detail", detail)
            except Exception:
                pass
            raise HTTPException(status_code=response.status_code, detail=detail)
        return response.json()


# ---------------------------------------------------------------------------
# POST /build — 接收文件，创建图谱元数据，转发到 AI 引擎
# ---------------------------------------------------------------------------

@router.post("/build")
async def start_kg_build(
    file: UploadFile = File(...),
    course_id: int | None = Form(None),
    current_user: dict = Depends(get_current_user_optional),
):
    """提交知识图谱构建任务 — 创建元数据记录后转发到 AI 引擎

    流程：
      1. 保存上传文件到临时目录
      2. 创建 KgGraph 元数据记录（status=pending），绑定 course_id（学科）
      3. 将 kg_graph_id 映射存入 Redis（供 status 轮询使用）
      4. 转发到 AI 引擎 /kg/build，携带 graph_name
      5. 返回 task_id + kg_graph_id 给前端
    """
    os.makedirs(KG_UPLOAD_DIR, exist_ok=True)

    file_path = os.path.join(KG_UPLOAD_DIR, file.filename or "upload")
    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    # 创建图谱元数据记录
    kg_service = KgGraphService()
    async with async_session() as db:
        kg_record = await kg_service.create_graph(
            original_filename=file.filename or "upload",
            file_path=file_path,
            db=db,
            course_id=course_id,
        )

    # 转发到 AI 引擎，携带 graph_name
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{settings.AI_SERVICE_URL}/kg/build",
            headers=_ai_headers(),
            json={
                "file_path": file_path,
                "graph_name": kg_record.graph_name,
                "kg_graph_id": kg_record.id,
            },
        )
        if response.status_code >= 400:
            detail = response.text
            try:
                detail = response.json().get("detail", detail)
            except Exception:
                pass
            raise HTTPException(status_code=response.status_code, detail=detail)
        result = response.json()

    task_id = result.get("task_id", "")

    # 将 task_id -> kg_graph_id 映射存入 Redis（供轮询时使用，24h 过期）
    if task_id:
        r = aioredis.from_url(settings.REDIS_URL)
        try:
            await r.set(f"kg:task_map:{task_id}", str(kg_record.id), ex=86400)
            # 反向映射：kg_graph_id -> task_id（供 list_graphs 对账使用）
            await r.set(f"kg:graph_task:{kg_record.id}", task_id, ex=86400)
        finally:
            await r.aclose()

    result["kg_graph_id"] = kg_record.id
    return result


# ---------------------------------------------------------------------------
# GET /build/status/{task_id} — 查询构建状态，完成时更新 PostgreSQL
# ---------------------------------------------------------------------------

@router.get("/build/status/{task_id}")
async def get_build_status(task_id: str, request: Request):
    """查询构建任务状态，完成或失败时自动更新 PostgreSQL 统计

    流程：
      1. 代理转发到 AI 引擎获取状态
      2. 如果状态为 completed/failed，从 Redis 取 kg_graph_id
      3. 更新 KgGraph 的 node_count / edge_count / chunk_count / status
    """
    result = await _proxy(request, "GET", f"/kg/build/status/{task_id}")

    # 如果任务已完成或失败，更新 PostgreSQL 统计
    status = result.get("status")
    if status in ("completed", "failed"):
        # 从 Redis 获取 kg_graph_id
        r = aioredis.from_url(settings.REDIS_URL)
        try:
            kg_graph_id_raw = await r.get(f"kg:task_map:{task_id}")
        finally:
            await r.aclose()

        kg_graph_id = int(kg_graph_id_raw) if kg_graph_id_raw else None

        if kg_graph_id:
            async with async_session() as db:
                kg_service = KgGraphService()
                if status == "completed":
                    # 获取构建结果
                    result_data = await _proxy(request, "GET", f"/kg/build/result/{task_id}")
                    node_count = result_data.get("nodes", 0)
                    edge_count = result_data.get("edges", 0)
                    chunk_count = result_data.get("chunks", 0)
                    await kg_service.update_graph_stats(
                        graph_id=kg_graph_id,
                        node_count=node_count,
                        edge_count=edge_count,
                        chunk_count=chunk_count,
                        status="completed",
                        db=db,
                    )
                else:
                    await kg_service.update_graph_stats(
                        graph_id=kg_graph_id,
                        node_count=0,
                        edge_count=0,
                        chunk_count=0,
                        status="failed",
                        db=db,
                    )

    return result


# ---------------------------------------------------------------------------
# GET /build/result/{task_id} — 获取构建结果
# ---------------------------------------------------------------------------

@router.get("/build/result/{task_id}")
async def get_build_result(task_id: str, request: Request):
    """获取构建结果"""
    return await _proxy(request, "GET", f"/kg/build/result/{task_id}")


# ---------------------------------------------------------------------------
# GET /graph/data — 代理查询图数据（透传 graph_name）
# ---------------------------------------------------------------------------

@router.get("/graph/data")
async def get_graph_data(request: Request):
    """获取知识图谱全量数据"""
    return await _proxy(request, "GET", "/kg/graph/data")


# ---------------------------------------------------------------------------
# GET /graph/search — 代理搜索节点（透传 graph_name）
# ---------------------------------------------------------------------------

@router.get("/graph/search")
async def search_graph_nodes(request: Request):
    """搜索知识图谱节点"""
    return await _proxy(request, "GET", "/kg/graph/search")


# ---------------------------------------------------------------------------
# 节点/边 CRUD — 代理转发到 AI 引擎
# ---------------------------------------------------------------------------

@router.post("/graph/node")
async def create_node(request: Request, current_user: dict = Depends(get_current_user_optional)):
    """创建节点 — 代理到 AI 引擎"""
    return await _proxy(request, "POST", "/kg/graph/node")


@router.put("/graph/node/{node_id}")
async def update_node(node_id: str, request: Request, current_user: dict = Depends(get_current_user_optional)):
    """更新节点 — 代理到 AI 引擎"""
    return await _proxy(request, "PUT", f"/kg/graph/node/{node_id}")


@router.delete("/graph/node/{node_id}")
async def delete_node(node_id: str, request: Request, current_user: dict = Depends(get_current_user_optional)):
    """删除节点 — 代理到 AI 引擎"""
    return await _proxy(request, "DELETE", f"/kg/graph/node/{node_id}")


@router.post("/graph/edge")
async def create_edge(request: Request, current_user: dict = Depends(get_current_user_optional)):
    """创建边 — 代理到 AI 引擎"""
    return await _proxy(request, "POST", "/kg/graph/edge")


@router.put("/graph/edge")
async def update_edge(request: Request, current_user: dict = Depends(get_current_user_optional)):
    """更新边 — 代理到 AI 引擎"""
    return await _proxy(request, "PUT", "/kg/graph/edge")


@router.delete("/graph/edge")
async def delete_edge(request: Request, current_user: dict = Depends(get_current_user_optional)):
    """删除边 — 代理到 AI 引擎"""
    return await _proxy(request, "DELETE", "/kg/graph/edge")
