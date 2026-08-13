"""Redis 队列消费者 — 从 registry 获取任务处理器"""

import json
import logging

import redis.asyncio as aioredis

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')

from app.config import settings
from app.tasks.registry import registry


async def start_worker():
    """启动 Redis 队列消费者

    任务分发逻辑完全由 registry 驱动：
    - 新增任务类型？只需在任务文件上加 @task_handler("type")
    - 无需修改本文件
    """
    registry.discover("app.tasks")

    r = aioredis.from_url(settings.REDIS_URL)
    while True:
        _, task_bytes = await r.brpop("chuma:tasks")
        task_data = json.loads(task_bytes)
        task_type = task_data.get("type")

        entry = registry.get(task_type)
        if entry is None:
            # TODO: 日志记录未知任务类型
            continue

        await entry.handler(task_data)
