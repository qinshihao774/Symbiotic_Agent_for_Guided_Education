"""任务注册中心 — 自发现式任务管理

所有任务通过装饰器自注册，worker 和 scheduler 从 registry 读取。
新增任务只需创建文件 + 装饰器，无需修改 worker/scheduler。

Usage:
    from app.tasks.registry import task_handler, scheduled_task

    @task_handler("kg_extract")
    async def run_extraction(task_data: dict):
        ...

    @scheduled_task("daily_profile", trigger="cron", hour=4, minute=0)
    async def update_student_profiles():
        ...
"""

import importlib
import pkgutil
from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class TaskEntry:
    task_type: str
    handler: Callable
    schedule: dict[str, Any] | None = None


class TaskRegistry:
    def __init__(self):
        self._tasks: dict[str, TaskEntry] = {}

    def register(self, task_type: str, handler: Callable, schedule: dict[str, Any] | None = None):
        """注册一个任务处理器"""
        self._tasks[task_type] = TaskEntry(task_type=task_type, handler=handler, schedule=schedule)

    def get(self, task_type: str) -> TaskEntry | None:
        """根据任务类型查找处理器"""
        return self._tasks.get(task_type)

    def all_tasks(self) -> list[TaskEntry]:
        """返回所有已注册任务"""
        return list(self._tasks.values())

    def scheduled_tasks(self) -> list[TaskEntry]:
        """返回所有定时任务"""
        return [t for t in self._tasks.values() if t.schedule is not None]

    def discover(self, package_name: str = "app.tasks"):
        """自动扫描并导入指定包下的所有模块，触发装饰器注册"""
        package = importlib.import_module(package_name)
        for _, module_name, _ in pkgutil.iter_modules(package.__path__):
            if module_name == "registry":
                continue
            importlib.import_module(f"{package_name}.{module_name}")


# 全局 registry 实例
registry = TaskRegistry()


def task_handler(task_type: str):
    """装饰器：注册一个队列任务"""
    def decorator(func: Callable):
        registry.register(task_type, func)
        return func
    return decorator


def scheduled_task(task_type: str, trigger: str = "cron", **schedule_kwargs):
    """装饰器：注册一个定时任务

    schedule_kwargs 传递给 APScheduler，如 hour=4, minute=0, day_of_week="mon-fri"
    """
    def decorator(func: Callable):
        schedule = {"trigger": trigger, **schedule_kwargs}
        registry.register(task_type, func, schedule=schedule)
        return func
    return decorator
