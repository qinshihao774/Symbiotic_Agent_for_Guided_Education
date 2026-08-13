"""定时任务调度器 — 从 registry 读取定时任务并注册到 APScheduler"""

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.tasks.registry import registry

scheduler = AsyncIOScheduler()


def start_scheduler():
    """扫描 registry 中所有带 schedule 的任务，注册到 APScheduler

    定时配置（cron 表达式）由各任务文件的 @scheduled_task 装饰器声明，
    调度器只需读取，无需硬编码。
    """
    registry.discover("app.tasks")

    for entry in registry.scheduled_tasks():
        scheduler.add_job(
            entry.handler,
            id=entry.task_type,
            **entry.schedule,
        )

    scheduler.start()


def stop_scheduler():
    scheduler.shutdown()
