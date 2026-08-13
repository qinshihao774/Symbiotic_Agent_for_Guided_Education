"""知识图谱管理路由"""

import asyncio
import json
import uuid

import redis.asyncio as aioredis
from fastapi import APIRouter, Body, Depends, HTTPException

from app.config import settings
from app.kg_pipeline.models import PipelineResult
from app.kg_pipeline.queries import GraphQueryError, get_full_graph, search_nodes
from app.ocr.schemas import TaskSubmitResponse


router = APIRouter()


@router.post("/build", response_model=TaskSubmitResponse)
async def start_kg_build(
    file_path: str = Body(..., embed=True),
    graph_name: str | None = Body(default=None, embed=True),
    kg_graph_id: int | None = Body(default=None, embed=True),
):
    """提交知识图谱构建任务（异步）"""
    task_id = str(uuid.uuid4())

    r = aioredis.from_url(settings.REDIS_URL)
    await r.lpush("chuma:tasks", json.dumps({
        "type": "kg_build",
        "task_id": task_id,
        "file_path": file_path,
        "output_key": f"kg:result:{task_id}",
        "graph_name": graph_name,
        "kg_graph_id": kg_graph_id,
    }))

    return TaskSubmitResponse(
        task_id=task_id,
        status="pending",
        status_url=f"/kg/build/status/{task_id}",
        result_url=f"/kg/build/result/{task_id}",
    )


@router.get("/build/status/{task_id}")
async def get_build_status(task_id: str):
    """查询构建任务状态"""
    r = aioredis.from_url(settings.REDIS_URL)
    result = await r.get(f"kg:result:{task_id}")
    if result is None:
        return {"task_id": task_id, "status": "processing"}
    return json.loads(result)


@router.get("/build/result/{task_id}")
async def get_build_result(task_id: str):
    """获取构建结果"""
    r = aioredis.from_url(settings.REDIS_URL)
    result = await r.get(f"kg:result:{task_id}")
    if result is None:
        raise HTTPException(status_code=404, detail="Result not found")
    return PipelineResult.model_validate_json(result)


@router.get("/graph/data")
async def get_graph_data(graph_name: str | None = None):
    """获取知识图谱全量数据（节点 + 边 + 统计）"""
    try:
        data = await asyncio.get_event_loop().run_in_executor(
            None, get_full_graph, graph_name
        )
        return data
    except GraphQueryError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/graph/search")
async def search_graph_nodes(q: str, graph_name: str | None = None):
    """按名称搜索实体节点"""
    try:
        results = await asyncio.get_event_loop().run_in_executor(
            None, search_nodes, q, graph_name
        )
        return {"results": results}
    except GraphQueryError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.post("/graph/delete")
async def delete_graph_data(graph_name: str):
    """清空并删除指定 AGE 图"""
    from app.kg_pipeline.storage import AgeStorage
    try:
        storage = AgeStorage(graph_name=graph_name)
        storage.drop_graph()
        return {"status": "ok", "graph_name": graph_name}
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


# ---------------------------------------------------------------------------
# 节点/边 CRUD — 供知识图谱编辑使用
# ---------------------------------------------------------------------------

from app.dependencies import verify_service_token
from app.schemas.kg_crud import (
    NodeCreateRequest, NodeUpdateRequest, NodeResponse, NodeDeleteResponse,
    EdgeCreateRequest, EdgeUpdateRequest, EdgeResponse, EdgeDeleteResponse,
)
from app.kg_pipeline.storage import AgeStorage, AgeConnectionError


def _age_error_to_http(e: AgeConnectionError, default_status: int = 502):
    """将 AgeConnectionError 转为 HTTPException

    - 包含 "not found" → 404
    - 包含 "already exists" → 409
    - 其他 → default_status
    """
    msg = str(e)
    if "not found" in msg.lower():
        raise HTTPException(status_code=404, detail=msg)
    if "already exists" in msg.lower():
        raise HTTPException(status_code=409, detail=msg)
    raise HTTPException(status_code=default_status, detail=msg)


@router.post(
    "/graph/node",
    response_model=NodeResponse,
    dependencies=[Depends(verify_service_token)],
)
async def create_node(req: NodeCreateRequest):
    """创建单个节点"""
    try:
        storage = AgeStorage(graph_name=req.graph_name)
        result = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: storage.create_node(
                name=req.name, ntype=req.type, description=req.description
            ),
        )
        return result
    except AgeConnectionError as e:
        raise _age_error_to_http(e)


@router.put(
    "/graph/node/{node_id}",
    response_model=NodeResponse,
    dependencies=[Depends(verify_service_token)],
)
async def update_node(node_id: str, req: NodeUpdateRequest):
    """更新节点属性"""
    try:
        storage = AgeStorage(graph_name=req.graph_name)
        fields = {k: v for k, v in req.model_dump().items()
                  if k != "graph_name" and v is not None}
        result = await asyncio.get_event_loop().run_in_executor(
            None, lambda: storage.update_node(node_id, **fields)
        )
        return result
    except AgeConnectionError as e:
        raise _age_error_to_http(e)


@router.delete(
    "/graph/node/{node_id}",
    response_model=NodeDeleteResponse,
    dependencies=[Depends(verify_service_token)],
)
async def delete_node(node_id: str, graph_name: str):
    """删除节点及其关联边"""
    try:
        storage = AgeStorage(graph_name=graph_name)
        deleted_id, edge_count = await asyncio.get_event_loop().run_in_executor(
            None, lambda: storage.delete_node(node_id)
        )
        return NodeDeleteResponse(
            deleted_node_id=deleted_id, deleted_edge_count=edge_count
        )
    except AgeConnectionError as e:
        raise _age_error_to_http(e)


@router.post(
    "/graph/edge",
    response_model=EdgeResponse,
    dependencies=[Depends(verify_service_token)],
)
async def create_edge(req: EdgeCreateRequest):
    """创建边"""
    try:
        storage = AgeStorage(graph_name=req.graph_name)
        result = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: storage.create_edge(
                source_id=req.source_node_id,
                target_id=req.target_node_id,
                relationship_name=req.relationship_name,
                description=req.description,
            ),
        )
        return result
    except AgeConnectionError as e:
        raise _age_error_to_http(e)


@router.put(
    "/graph/edge",
    response_model=EdgeResponse,
    dependencies=[Depends(verify_service_token)],
)
async def update_edge(req: EdgeUpdateRequest):
    """更新边属性"""
    try:
        storage = AgeStorage(graph_name=req.graph_name)
        fields = {k: v for k, v in req.model_dump().items()
                  if k not in ("graph_name", "source_node_id", "target_node_id")
                  and v is not None}
        result = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: storage.update_edge(
                req.source_node_id, req.target_node_id, **fields
            ),
        )
        return result
    except AgeConnectionError as e:
        raise _age_error_to_http(e)


@router.delete(
    "/graph/edge",
    response_model=EdgeDeleteResponse,
    dependencies=[Depends(verify_service_token)],
)
async def delete_edge(graph_name: str, source_node_id: str, target_node_id: str):
    """删除边"""
    try:
        storage = AgeStorage(graph_name=graph_name)
        src, tgt = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: storage.delete_edge(source_node_id, target_node_id),
        )
        return EdgeDeleteResponse(source_node_id=src, target_node_id=tgt)
    except AgeConnectionError as e:
        raise _age_error_to_http(e)
