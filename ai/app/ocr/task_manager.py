"""OCR 异步任务管理器 — 从 mineru-api 精简移植"""

import asyncio
import os
import uuid
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from loguru import logger

from app.config import settings
from app.ocr.schemas import OcrParseParams, StoredUpload, utc_now_iso
from app.ocr.service import cleanup_file, create_result_zip, run_ocr_parse

TASK_PENDING = "pending"
TASK_PROCESSING = "processing"
TASK_COMPLETED = "completed"
TASK_FAILED = "failed"
TASK_TERMINAL_STATES = {TASK_COMPLETED, TASK_FAILED}


@dataclass
class OcrTask:
    """OCR 解析任务"""

    task_id: str
    status: str
    file_names: list[str]
    created_at: str
    output_dir: str
    params: OcrParseParams
    server_url: str
    upload_names: list[str]
    uploads: list[str]
    submit_order: int = 0
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error: Optional[str] = None

    def to_status_payload(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "status": self.status,
            "file_names": self.file_names,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "error": self.error,
        }


class AsyncTaskManager:
    """异步 OCR 任务管理器"""

    def __init__(self):
        self.tasks: dict[str, OcrTask] = {}
        self.task_events: dict[str, asyncio.Event] = {}
        self.queue: asyncio.Queue[str] = asyncio.Queue()
        self.dispatcher_task: Optional[asyncio.Task] = None
        self.cleanup_task: Optional[asyncio.Task] = None
        self.active_tasks: set[asyncio.Task] = set()
        self.last_worker_error: Optional[str] = None
        self.is_shutting_down = False
        self._next_submit_order = 1
        self._request_semaphore = asyncio.Semaphore(settings.OCR_MAX_CONCURRENT)

    def _get_output_root(self) -> str:
        """获取输出根目录"""
        root = os.path.abspath(settings.OCR_OUTPUT_DIR)
        os.makedirs(root, exist_ok=True)
        return root

    async def start(self) -> None:
        """启动任务调度器和清理器"""
        self.is_shutting_down = False
        self.last_worker_error = None
        if self.dispatcher_task is None or self.dispatcher_task.done():
            self.dispatcher_task = asyncio.create_task(
                self._dispatcher_loop(), name="ocr-task-dispatcher"
            )
        if settings.OCR_TASK_RETENTION_SECONDS > 0:
            if self.cleanup_task is None or self.cleanup_task.done():
                self.cleanup_task = asyncio.create_task(
                    self._cleanup_loop(), name="ocr-task-cleanup"
                )
        logger.info(
            f"AsyncTaskManager started, max_concurrent={settings.OCR_MAX_CONCURRENT}"
        )

    async def shutdown(self) -> None:
        """关闭任务管理器"""
        self.is_shutting_down = True
        self._wake_waiters()
        if self.dispatcher_task is not None:
            self.dispatcher_task.cancel()
            with suppress(asyncio.CancelledError):
                await self.dispatcher_task
            self.dispatcher_task = None
        if self.cleanup_task is not None:
            self.cleanup_task.cancel()
            with suppress(asyncio.CancelledError):
                await self.cleanup_task
            self.cleanup_task = None
        pending = list(self.active_tasks)
        for t in pending:
            t.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
        self.active_tasks.clear()
        logger.info("AsyncTaskManager shut down")

    async def submit(
        self,
        file_names: list[str],
        upload_names: list[str],
        uploads: list[str],
        params: OcrParseParams,
    ) -> OcrTask:
        """提交新的 OCR 任务"""
        task_id = str(uuid.uuid4())
        output_dir = f"{self._get_output_root()}/{task_id}"
        os.makedirs(output_dir, exist_ok=True)

        task = OcrTask(
            task_id=task_id,
            status=TASK_PENDING,
            file_names=file_names,
            created_at=utc_now_iso(),
            output_dir=output_dir,
            params=params,
            server_url=settings.OCR_VLM_URL,
            upload_names=upload_names,
            uploads=uploads,
            submit_order=self._next_submit_order,
        )
        self._next_submit_order += 1
        self.tasks[task_id] = task
        self.task_events[task_id] = asyncio.Event()
        await self.queue.put(task_id)
        logger.info(f"OCR task submitted: {task_id}, files={file_names}")
        return task

    def get(self, task_id: str) -> Optional[OcrTask]:
        return self.tasks.get(task_id)

    def get_status_payload(self, task: OcrTask) -> dict[str, Any]:
        return task.to_status_payload()

    async def wait_for_terminal_state(self, task_id: str) -> OcrTask:
        """等待任务进入终态 (completed/failed)"""
        task = self.tasks.get(task_id)
        if task is None:
            raise RuntimeError("Task not found")
        if task.status in TASK_TERMINAL_STATES:
            return task

        task_event = self.task_events.get(task_id)
        if task_event is None:
            raise RuntimeError("Task event not available")

        await task_event.wait()
        task = self.tasks.get(task_id)
        if task is None:
            raise RuntimeError("Task was removed")
        return task

    def get_result_zip_path(self, task: OcrTask) -> str:
        """生成结果 ZIP 并返回路径"""
        return create_result_zip(task.output_dir, task.file_names)

    def _wake_waiters(self) -> None:
        for event in self.task_events.values():
            event.set()

    def _signal_task_event(self, task_id: str) -> None:
        event = self.task_events.get(task_id)
        if event is not None:
            event.set()

    async def _dispatcher_loop(self) -> None:
        """任务分发循环"""
        try:
            while True:
                task_id = await self.queue.get()
                processor = asyncio.create_task(
                    self._process_task(task_id),
                    name=f"ocr-task-{task_id}",
                )
                self.active_tasks.add(processor)
                processor.add_done_callback(self._on_processor_done)
                self.queue.task_done()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self.last_worker_error = str(exc)
            self._wake_waiters()
            logger.exception("Task dispatcher crashed")
            raise

    async def _cleanup_loop(self) -> None:
        """过期任务清理循环"""
        try:
            while True:
                await asyncio.sleep(300)  # 每 5 分钟清理一次
                self._cleanup_expired_tasks()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.exception("Task cleanup loop crashed")
            raise

    def _on_processor_done(self, processor: asyncio.Task) -> None:
        self.active_tasks.discard(processor)
        if processor.cancelled():
            return
        exc = processor.exception()
        if exc is not None:
            logger.error(f"Task processor crashed: {exc}")
            self.last_worker_error = str(exc)

    async def _process_task(self, task_id: str) -> None:
        """处理单个 OCR 任务"""
        task = self.tasks.get(task_id)
        if task is None:
            return

        try:
            async with self._request_semaphore:
                await self._run_task(task)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            task.status = TASK_FAILED
            task.error = str(exc)
            task.completed_at = utc_now_iso()
            self._signal_task_event(task_id)
            logger.exception(f"OCR task failed: {task_id}")

    async def _run_task(self, task: OcrTask) -> None:
        """执行 OCR 解析"""
        task.status = TASK_PROCESSING
        task.started_at = utc_now_iso()
        task.error = None

        # 重建 StoredUpload 列表
        uploads = [
            StoredUpload(
                original_name=upload_name,
                stem=file_name,
                path=upload_path,
            )
            for upload_name, file_name, upload_path in zip(
                task.upload_names, task.file_names, task.uploads
            )
        ]

        await run_ocr_parse(
            output_dir=task.output_dir,
            uploads=uploads,
            params=task.params,
            server_url=task.server_url,
        )

        task.status = TASK_COMPLETED
        task.completed_at = utc_now_iso()
        self._signal_task_event(task.task_id)
        logger.info(f"OCR task completed: {task.task_id}")

    def _cleanup_expired_tasks(self) -> int:
        """清理过期的已完成任务"""
        if settings.OCR_TASK_RETENTION_SECONDS <= 0:
            return 0

        now = datetime.now(timezone.utc)
        expired_ids = []
        for task_id, task in self.tasks.items():
            if task.status not in TASK_TERMINAL_STATES:
                continue
            if not task.completed_at:
                continue
            try:
                completed_at = datetime.fromisoformat(task.completed_at)
            except ValueError:
                continue
            if completed_at.tzinfo is None:
                completed_at = completed_at.replace(tzinfo=timezone.utc)
            if (now - completed_at).total_seconds() >= settings.OCR_TASK_RETENTION_SECONDS:
                expired_ids.append(task_id)

        for task_id in expired_ids:
            task = self.tasks.pop(task_id, None)
            if task is None:
                continue
            self.task_events.pop(task_id, None)
            cleanup_file(task.output_dir)
            logger.info(f"Cleaned expired OCR task: {task_id}")
        return len(expired_ids)
