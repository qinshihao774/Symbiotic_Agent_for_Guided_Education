"""知识图谱路由"""

from fastapi import APIRouter, Depends, HTTPException

from app.core.database import async_session
from app.core.deps import get_current_user_optional
from app.schemas.kg_graph import KgGraphResponse
from app.services.kg_graph_service import KgGraphService

router = APIRouter()


@router.get("/graphs", response_model=list[KgGraphResponse])
async def list_graphs(current_user: dict = Depends(get_current_user_optional)):
    """获取所有知识图谱列表（含 pending 状态自动对账）"""
    kg_service = KgGraphService()
    async with async_session() as db:
        graphs = await kg_service.list_graphs(db)
        # 对账：将 Redis 中已完成但 PostgreSQL 还卡在 pending 的图谱状态同步过来
        graphs = await kg_service.reconcile_pending_graphs(graphs, db)
    return graphs


@router.get("/graphs/{graph_id}/stats")
async def get_graph_stats(graph_id: int):
    """获取图谱资源统计（供删除确认用）"""
    from sqlalchemy import text

    kg_service = KgGraphService()
    async with async_session() as db:
        kg_record = await kg_service.get_graph_by_id(graph_id, db)
        if kg_record is None:
            raise HTTPException(status_code=404, detail="图谱不存在")

        result = await db.execute(
            text("SELECT COUNT(*) FROM document_chunks WHERE kg_graph_id = :gid"),
            {"gid": graph_id},
        )
        chunk_count = result.scalar() or 0

    return {
        "graph_id": graph_id,
        "graph_name": kg_record.graph_name,
        "original_filename": kg_record.original_filename,
        "node_count": kg_record.node_count,
        "edge_count": kg_record.edge_count,
        "chunk_count": chunk_count,
        "status": kg_record.status,
    }


@router.delete("/graphs/{graph_id}")
async def delete_graph(
    graph_id: int,
    current_user: dict = Depends(get_current_user_optional),
):
    """删除知识图谱（同时清理 AGE 图、document_chunks 和本地文件）"""
    import logging

    logger = logging.getLogger(__name__)
    kg_service = KgGraphService()

    # Step 1: Verify graph exists and get graph_name (without deleting yet)
    async with async_session() as db:
        kg_record = await kg_service.get_graph_by_id(graph_id, db)
        if kg_record is None:
            raise HTTPException(status_code=404, detail="图谱不存在")
        if kg_record.status == "pending":
            raise HTTPException(status_code=400, detail="图谱正在构建中，无法删除")
        graph_name = kg_record.graph_name

    # Step 1.5: Delete document_chunks for this graph
    from sqlalchemy import text

    async with async_session() as db:
        await db.execute(
            text("DELETE FROM document_chunks WHERE kg_graph_id = :gid"),
            {"gid": graph_id},
        )
        await db.commit()

    # Step 2: Call AI engine to clear AGE graph (before deleting DB record)
    try:
        import httpx
        from app.core.config import settings

        async with httpx.AsyncClient(timeout=30.0) as client:
            await client.post(
                f"{settings.AI_SERVICE_URL}/kg/graph/delete",
                headers={"X-Service-Token": settings.AI_SERVICE_TOKEN},
                params={"graph_name": graph_name},
            )
    except Exception as e:
        logger.warning(f"Failed to clear AGE graph {graph_name}: {e}")

    # Step 3: Delete PostgreSQL record and local file
    async with async_session() as db:
        await kg_service.delete_graph(graph_id, db)

    return {"status": "ok", "graph_id": graph_id}


@router.get("/graph")
async def get_knowledge_graph():
    """获取知识图谱数据（节点+边），用于前端 ECharts 可视化"""
    pass


@router.get("/nodes/{node_id}")
async def get_node_detail(node_id: int):
    """获取单个知识点详情（关联题目、资源、前置知识）"""
    pass


@router.get("/nodes/{node_id}/questions")
async def get_node_questions(node_id: int):
    """获取某知识点下的练习题"""
    pass
