"""知识图谱抽取任务 — 从教材/课件中提取知识点和关系"""

import uuid

from app.tasks.registry import task_handler


@task_handler("kg_extract")
async def run_extraction(task_data: dict):
    """执行知识图谱抽取（由 Redis 队列触发）"""
    task_id = task_data.get("task_id", str(uuid.uuid4()))
    # TODO: 实现 LLM 抽取逻辑
    # 1. 读取教材文本
    # 2. 调用 LLM 抽取知识点和关系
    # 3. 存入 ChromaDB 和 data/kg/
    # 4. 更新任务状态到 Redis
    pass
