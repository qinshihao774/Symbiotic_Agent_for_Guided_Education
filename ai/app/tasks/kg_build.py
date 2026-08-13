"""知识图谱构建异步任务 — 由 Redis 队列触发"""

import json
import logging

import redis.asyncio as aioredis

from app.config import settings
from app.kg_pipeline.pipeline import KGPipeline
from app.kg_pipeline.models import PipelineResult
from app.tasks.registry import task_handler


logger = logging.getLogger(__name__)


@task_handler("kg_build")
async def run_kg_build(task_data: dict):
    """执行知识图谱构建任务

    task_data:
    {
        "task_id": "uuid",
        "file_path": "/path/to/document.pdf",
        "output_key": "kg:result:{task_id}",
        "graph_name": "kg_xxx"  # 可选
    }
    """
    task_id = task_data.get("task_id", "unknown")
    file_path = task_data["file_path"]
    output_key = task_data.get("output_key", f"kg:result:{task_id}")
    graph_name = task_data.get("graph_name")  # 可选，为空则从数据库 kg_graphs 解析默认图谱
    kg_graph_id = task_data.get("kg_graph_id")  # 可选，入库时关联 graph 记录

    logger.info(f"[KGBuild] Task {task_id}: building KG from {file_path} (kg_graph_id={kg_graph_id})")

    try:
        pipeline = KGPipeline(graph_name=graph_name)
        result = await pipeline.run_from_file(file_path, kg_graph_id=kg_graph_id)
    except Exception as e:
        logger.error(f"[KGBuild] Task {task_id} crashed: {e}", exc_info=True)
        result = PipelineResult(status="failed", error=str(e))

    r = aioredis.from_url(settings.REDIS_URL)
    await r.set(output_key, result.model_dump_json(), ex=86400)

    logger.info(f"[KGBuild] Task {task_id}: {result.status}")
