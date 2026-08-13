"""Agent 工具环境上下文 — 通过 contextvars 在线程/协程间传递教材过滤参数"""

from contextvars import ContextVar

current_kg_graph_ids: ContextVar[list[int]] = ContextVar("kg_graph_ids", default=[])
current_graph_names: ContextVar[list[str]] = ContextVar("graph_names", default=[])