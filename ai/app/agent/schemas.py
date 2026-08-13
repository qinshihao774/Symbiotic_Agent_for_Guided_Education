"""Agent 模块数据结构"""
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class AgentChatRequest(BaseModel):
    """Agent 对话请求"""
    user_id: int = 1  # TODO 暂时默认 1，登录实现后改为必填
    message: str
    history: list[dict] = Field(default_factory=list)
    kg_graph_ids: list[int] = Field(default_factory=list)
    graph_names: list[str] = Field(default_factory=list)
    message_id: str = Field(default_factory=lambda: f"msg_{uuid4().hex}")


@dataclass
class ToolDef:
    """工具定义 — 本地或 MCP 工具的统一描述"""
    name: str
    description: str
    parameters: dict          # JSON Schema for the tool's parameters
    handler: Callable[..., Awaitable[str]] | None = None  # None for MCP tools
    is_mcp: bool = False
    display_name: str | None = None
    purpose: str | None = None

    def to_openai_format(self) -> dict:
        """转为 OpenAI function-calling 格式"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


@dataclass
class ToolExecutionResult:
    """工具的内部结果与公开展示摘要。

    raw 仅提供给模型，绝不直接发送到浏览器。
    """

    raw: str
    success: bool
    summary: str
    duration_ms: int
    metrics: dict[str, int | float | str]
    error_code: str | None = None
    error_message: str | None = None
    retryable: bool = False
